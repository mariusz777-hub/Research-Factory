from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .artifacts import ArtifactStore
from .models import Comparison, Job, ModelResponse, Project, Question, ResearchSource, Run


def _read_optional(artifacts: ArtifactStore, relative: str) -> str:
    if not relative:
        return ""
    path = artifacts.resolve_public(relative)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_artifact_manifest(artifacts: ArtifactStore, base: Path) -> str:
    root = artifacts.resolve_public(base.as_posix())
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if path.name == "artifact_manifest.json" or relative == "logs/events.jsonl":
            continue
        data = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return artifacts.write_json(
        base / "artifact_manifest.json",
        {"artifacts": entries, "excluded_append_only": ["logs/events.jsonl"]},
    )


def build_report(session: Session, run_id: str, artifacts: ArtifactStore) -> tuple[str, str]:
    run = session.get(Run, run_id)
    if run is None:
        raise KeyError(run_id)
    project = session.get(Project, run.project_id)
    questions = list(
        session.scalars(select(Question).where(Question.run_id == run_id).order_by(Question.ordinal))
    )
    jobs = list(session.scalars(select(Job).where(Job.run_id == run_id)))
    responses = list(session.scalars(select(ModelResponse).where(ModelResponse.run_id == run_id)))
    comparisons = list(session.scalars(select(Comparison).where(Comparison.run_id == run_id)))
    sources = list(session.scalars(select(ResearchSource).where(ResearchSource.run_id == run_id)))
    response_by_question: dict[str, list[ModelResponse]] = {}
    for response in responses:
        response_by_question.setdefault(response.question_id, []).append(response)
    comparison_by_question = {item.question_id: item for item in comparisons}
    status_counts = Counter(
        "SUCCESS" if job.job_type == "REPORT" and job.status == "RUNNING" else job.status
        for job in jobs
    )
    type_counts = Counter(job.job_type for job in jobs)
    failed_jobs = [job for job in jobs if job.status == "FAILED"]
    projected_status = "PARTIAL" if failed_jobs else "COMPLETE"

    base = artifacts.run_root(project.slug, run_id).relative_to(artifacts.root)
    architecture = _read_optional(artifacts, (base / "reports" / "architecture.md").as_posix())
    backlog = _read_optional(artifacts, (base / "reports" / "backlog.md").as_posix())
    user_stories = _read_optional(artifacts, (base / "reports" / "user_stories.md").as_posix())
    gherkin = _read_optional(artifacts, (base / "reports" / "specification.feature").as_posix())
    project_structure = _read_optional(
        artifacts, (base / "reports" / "project_structure.md").as_posix()
    )
    coding_prompt = _read_optional(artifacts, (base / "reports" / "coding_prompt.md").as_posix())
    executive = _read_optional(artifacts, (base / "reports" / "executive_summary.md").as_posix())

    lines = [
        f"# Raport badawczo-analityczny: {project.name}",
        "",
        f"**Run:** `{run.id}`  ",
        f"**Status:** `{projected_status}`  ",
        f"**Modele:** {', '.join(project.selected_models)}  ",
        f"**Zakres researchu:** {', '.join(project.selected_scopes) or 'brak'}",
        "",
        "## Pomysł",
        "",
        project.idea,
        "",
        "## Kompletność wykonania",
        "",
        f"- Pytania: **{len(questions)}**",
        f"- Oczekiwane odpowiedzi modeli: **{len(questions) * len(project.selected_models)}**",
        f"- Zapisane odpowiedzi: **{len(responses)}**",
        f"- Porównania: **{len(comparisons)}/{len(questions)}**",
        f"- Źródła GitHub/Reddit/Google/WWW: **{len(sources)}**",
        f"- Statusy zadań: `{dict(status_counts)}`",
        f"- Typy zadań: `{dict(type_counts)}`",
        f"- Budżet wywołań: **{run.model_calls_started}/{run.model_call_limit}**",
        f"- Budżet tokenów: **{run.tokens_used}/{run.token_limit}** (wartości estymowane, gdy provider nie zwraca usage)",
        "",
    ]
    if executive:
        lines += ["## Synteza wykonawcza", "", executive.strip(), ""]

    lines += ["## Research GitHub, Reddit, Google i WWW", ""]
    if sources:
        for source in sources:
            detail = f" — {source.snippet.strip()}" if source.snippet.strip() else ""
            lines.append(
                f"- [{source.title}]({source.url}) ({source.source_type}, "
                f"{source.verification_status}, pobrano {source.created_at.isoformat()}){detail}"
            )
    else:
        lines.append("Brak zapisanych źródeł; sprawdź status zadań researchu.")
    lines.append("")

    lines += ["## Analiza pytań i porównanie modeli", ""]
    for question in questions:
        lines += [f"### {question.ordinal}. {question.template_id}", "", question.rendered_prompt, ""]
        for response in sorted(response_by_question.get(question.id, []), key=lambda item: item.model_name):
            lines += [f"#### {response.model_name} ({response.provider_model})", "", response.content, ""]
        comparison = comparison_by_question.get(question.id)
        if comparison:
            lines += ["#### Zgodności", ""]
            if comparison.agreements:
                for item in comparison.agreements:
                    lines.append(f"- {item['claim']} _(modele: {', '.join(item['models'])})_")
            else:
                lines.append("- Nie wykryto stabilnych zgodności tekstowych.")
            lines += ["", "#### Sprzeczności", ""]
            if comparison.conflicts:
                for item in comparison.conflicts:
                    lines.append(
                        f"- **{item['reason']}** — {item['models'][0]}: {item['left']} / "
                        f"{item['models'][1]}: {item['right']}"
                    )
            else:
                lines.append("- Nie wykryto jawnych sprzeczności polaryzacji ani wartości liczbowych.")
            lines += ["", "#### Braki", ""]
            lines.extend(f"- {gap}" for gap in comparison.gaps)
            lines.append("")
        else:
            lines += ["_Brak porównania dla tego pytania._", ""]

    lines += [
        "## Architektura badanego projektu",
        "",
        architecture.strip() or "Brak syntezy architektury badanego projektu.",
        "",
    ]
    lines += ["## Backlog", "", backlog.strip() or "Brak wygenerowanego backlogu.", ""]
    lines += [
        "## User stories badanego projektu",
        "",
        user_stories.strip() or "Brak wygenerowanych user stories.",
        "",
    ]
    lines += [
        "## Specyfikacja Gherkin badanego projektu",
        "",
        "```gherkin",
        gherkin.strip() or "# Brak wygenerowanej specyfikacji Gherkin.",
        "```",
        "",
    ]
    lines += [
        "## Struktura katalogów i plików badanego projektu",
        "",
        project_structure.strip() or "Brak wygenerowanej struktury projektu.",
        "",
    ]
    lines += [
        "## Końcowy prompt do kodowania",
        "",
        coding_prompt.strip() or "Brak wygenerowanego promptu do kodowania.",
        "",
    ]
    lines += ["## Błędy i ograniczenia wykonania", ""]
    if failed_jobs:
        for job in failed_jobs:
            lines.append(f"- `{job.job_type}` / `{job.dedupe_key}`: {job.last_error}")
    else:
        lines.append("- Brak terminalnych błędów zadań.")
    lines += [
        "",
        "## Zakres etapu drugiego (niezrealizowany w MVP)",
        "",
        "Klonowanie repozytoriów, statyczna analiza kodu, uruchamianie w kontenerach, "
        "Neo4j, wyszukiwanie semantyczne, diagramy oraz eksport Word/PDF.",
        "",
    ]
    content = "\n".join(lines)
    report_path = artifacts.write_text(base / "reports" / "report.md", content)
    build_artifact_manifest(artifacts, base)
    return report_path, content
