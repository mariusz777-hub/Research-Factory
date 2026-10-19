import json

import pytest
from sqlalchemy import select

from research_factory.model_gateway import ModelResult
from research_factory.models import Comparison, Job, ModelResponse, ResearchSource, Run
from research_factory.orchestrator import Orchestrator
from research_factory.research import Source
from research_factory.schemas import ProjectCreate
from research_factory.worker import Worker


class FakeGateway:
    async def complete(self, model_name, prompt, system_prompt):
        if prompt.startswith("Na podstawie materiału"):
            text = json.dumps({
                "executive_summary": "Podsumowanie badanego projektu i jego najważniejszych decyzji MVP.",
                "architecture_markdown": "### Architektura badanego projektu\nWarstwa API korzysta z usług aplikacyjnych, domeny i adapterów infrastruktury. Dane są utrwalane transakcyjnie, a operacje mają identyfikatory korelacyjne i idempotencję.",
                "backlog_markdown": "### Backlog\n- Zbudować pionowy przepływ od API do trwałego zapisu.\n- Dodać walidację i obsługę błędów.\n- Dodać testy integracyjne, kryteria akceptacji i Definition of Done dla każdego przyrostu.",
                "user_stories_markdown": "# User stories\n- Jako użytkownik chcę wykonać główne zadanie, aby uzyskać mierzalny wynik.\n  - Kryteria: walidacja, sukces, błąd i audyt.\n- Jako operator chcę wznowić przerwaną operację bez duplikatu.",
                "gherkin_feature": "# language: pl\nFunkcja: Badany projekt\n  Założenia:\n    Zakładając poprawną konfigurację\n  Scenariusz: Sukces głównego procesu\n    Kiedy wykonuję poprawną operację\n    Wtedy otrzymuję zapisany wynik i identyfikator korelacyjny\n  Scenariusz: Błąd walidacji\n    Kiedy przekazuję błędne dane\n    Wtedy stan nie jest zmieniany i otrzymuję czytelny błąd",
                "project_structure_markdown": "# Struktura\n```text\nsrc/\n  domain/\n  application/\n  infrastructure/\n  api/\ntests/\n  unit/\n  integration/\n  acceptance/\n```\nDomena nie zależy od infrastruktury, a adaptery implementują porty aplikacyjne.",
                "coding_prompt_markdown": "# Coding prompt\nZaimplementuj badany projekt pionami funkcjonalnymi zgodnie z architekturą portów i adapterów. Dodaj walidację, idempotencję, bezpieczne sekrety, migracje i pełne testy unit, integration oraz acceptance. Nie deklaruj ukończenia bez uruchomienia testów i przedstawienia ich wyników.",
                "decisions": [], "risks": [],
            }, ensure_ascii=False)
        else:
            text = f"{model_name}: system powinien mieć PostgreSQL i odporną kolejkę. Źródło https://example.org."
        return ModelResult(model_name, "fake", text, {"ok": True}, 1)


class FakeResearch:
    def __init__(self, kind): self.kind = kind
    async def search(self, query):
        return [Source(self.kind, f"{self.kind} title", f"https://example.org/{self.kind}", "snippet", {})]


class FakeGoogle:
    async def search(self, query, input_text=""):
        return [Source("google", "google title", "https://example.org/google", input_text, {})]


@pytest.mark.asyncio
async def test_full_pipeline_is_resumable_and_complete(settings, session_factory, library):
    worker = Worker(
        settings, session_factory, gateway=FakeGateway(),
        github=FakeResearch("github"), reddit=FakeResearch("reddit"),
        google=FakeGoogle(), web=FakeResearch("web"), library=library,
    )
    orchestrator = Orchestrator(session_factory, settings, worker.artifacts, library)
    _, run = orchestrator.create_project(ProjectCreate(
        name="Pipeline", idea="Analiza kompletnego pomysłu w deterministycznym teście integracyjnym.",
        models=["openai", "gemini"], scopes=["github", "reddit", "google", "web"],
        google_research_input="Wynik https://example.org/google-input opis",
    ))
    for _ in range(150):
        worked = await worker.run_once()
        with session_factory() as session:
            status = session.scalar(select(Run.status).where(Run.id == run.id))
        if status == "COMPLETE":
            break
        if not worked:
            orchestrator.advance(run.id)
    assert status == "COMPLETE"
    with session_factory() as session:
        assert len(list(session.scalars(select(ModelResponse).where(ModelResponse.run_id == run.id)))) == 24
        assert len(list(session.scalars(select(Comparison).where(Comparison.run_id == run.id)))) == 12
        jobs = list(session.scalars(select(Job).where(Job.run_id == run.id)))
        assert all(job.status == "SUCCESS" for job in jobs)
        assert {"GITHUB_RESEARCH", "REDDIT_RESEARCH", "GOOGLE_RESEARCH", "WEB_RESEARCH"} <= {
            job.job_type for job in jobs
        }
        source_types = set(
            session.scalars(select(ResearchSource.source_type).where(ResearchSource.run_id == run.id))
        )
        assert source_types == {"github", "reddit", "google", "web"}
        finished = session.get(Run, run.id)
        assert finished.model_calls_started == 25
        assert finished.tokens_used > 0
    reports = list(settings.artifact_root.rglob("report.md"))
    assert len(reports) == 1
    report_text = reports[0].read_text(encoding="utf-8")
    assert "Architektura badanego projektu" in report_text
    reports_root = reports[0].parent
    assert (reports_root / "user_stories.md").is_file()
    assert (reports_root / "specification.feature").is_file()
    assert (reports_root / "project_structure.md").is_file()
    assert (reports_root / "coding_prompt.md").is_file()
    assert "Research Factory" not in (reports_root / "architecture.md").read_text(encoding="utf-8")
    synthesis_prompt = next(settings.artifact_root.rglob("prompts/synthesis.md"))
    assert "opisują WYŁĄCZNIE badany projekt" in synthesis_prompt.read_text(encoding="utf-8")
    manifests = list(settings.artifact_root.rglob("artifact_manifest.json"))
    assert len(manifests) == 1 and '"sha256"' in manifests[0].read_text(encoding="utf-8")
