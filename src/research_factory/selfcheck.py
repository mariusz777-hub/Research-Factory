from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from .model_gateway import ModelResult
from .models import Base, Run
from .orchestrator import Orchestrator
from .question_library import load_question_library
from .research import Source
from .schemas import ProjectCreate
from .settings import Settings
from .worker import Worker


class FakeGateway:
    async def complete(self, model_name: str, prompt: str, system_prompt: str) -> ModelResult:
        if prompt.startswith("Na podstawie materiału"):
            content = json.dumps(
                {
                    "executive_summary": "MVP ma kontrolowany przepływ, jawne braki i trwałe, audytowalne wyniki.",
                    "architecture_markdown": "### Komponenty badanego projektu\nAPI wywołuje warstwę aplikacyjną i domenę przez jawne porty. Adapter bazy zapewnia transakcje, idempotencję i audyt, a obserwowalność używa identyfikatora korelacyjnego.",
                    "backlog_markdown": "### Epic 1\n- Pionowy przepływ projektu z walidacją i kryteriami akceptacji.\n- Obsługa błędów i wznowienie bez duplikatów.\n\n### DoD\n- Testy jednostkowe, integracyjne i akceptacyjne przechodzą.",
                    "user_stories_markdown": "# User stories\n- Jako użytkownik chcę wykonać główny proces, aby uzyskać trwały wynik.\n  - Kryteria: sukces, walidacja, błąd i audyt.\n- Jako operator chcę bezpiecznie wznowić przerwane wykonanie.",
                    "gherkin_feature": "# language: pl\nFunkcja: Projekt Selfcheck\n  Założenia:\n    Zakładając poprawną konfigurację\n  Scenariusz: Główny proces\n    Kiedy wykonuję poprawną operację\n    Wtedy otrzymuję trwały wynik z identyfikatorem korelacyjnym\n  Scenariusz: Odrzucenie błędnych danych\n    Kiedy wykonuję operację z błędnymi danymi\n    Wtedy stan pozostaje bez zmian i otrzymuję opis błędu",
                    "project_structure_markdown": "# Struktura projektu\n```text\nsrc/\n  domain/\n  application/\n  infrastructure/\n  api/\ntests/\n  unit/\n  integration/\n  acceptance/\n```\nDomena nie importuje infrastruktury.",
                    "coding_prompt_markdown": "# Coding prompt\nZaimplementuj badany projekt pionami funkcjonalnymi. Zachowaj podział domena, aplikacja, adaptery i API. Dodaj walidację, transakcje, idempotencję, audyt, bezpieczną konfigurację sekretów oraz testy jednostkowe, integracyjne i akceptacyjne. Zakończ raportem z wykonanych testów.",
                    "decisions": [{"decision": "PostgreSQL jako źródło prawdy"}],
                    "risks": [{"risk": "Limity API", "mitigation": "next_attempt_at i backoff"}],
                },
                ensure_ascii=False,
            )
        else:
            content = (
                f"Model {model_name}: rekomendowany jest mały, testowalny MVP z PostgreSQL, "
                "kolejką odporną na restart oraz źródłami https://example.org."
            )
        return ModelResult(model_name, f"fake-{model_name}", content, {"fake": True}, 1)


class FakeGitHub:
    async def search(self, query: str):
        return [Source("github", "example/research", "https://github.com/example/research", "Przykładowe repozytorium", {"stars": 42})]


class FakeWeb:
    async def search(self, query: str):
        return [Source("web", "Przykładowe źródło", "https://example.org/research", "Opis źródła", {"provider": "fake"})]


class FakeReddit:
    async def search(self, query: str):
        return [Source("reddit", "Przykładowa dyskusja", "https://reddit.com/r/test/1", "Opis dyskusji", {"provider": "fake"})]


class FakeGoogle:
    async def search(self, query: str, input_text: str = ""):
        return [Source("google", "Google input", "https://example.org/google", input_text, {"provider": "fake"})]


async def run_selfcheck() -> Path:
    root = Path(tempfile.mkdtemp(prefix="research-factory-selfcheck-"))
    database = root / "selfcheck.db"
    engine = create_engine(f"sqlite:///{database}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    project_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        database_url=f"sqlite:///{database}",
        artifact_root=root / "artifacts",
        question_library=project_root / "config" / "question_templates.yaml",
        model_min_interval_seconds=0,
        worker_poll_seconds=0.1,
        job_max_attempts=2,
    )
    library = load_question_library(settings.question_library)
    worker = Worker(
        settings,
        factory,
        gateway=FakeGateway(),
        github=FakeGitHub(),
        reddit=FakeReddit(),
        google=FakeGoogle(),
        web=FakeWeb(),
        library=library,
    )
    orchestrator = Orchestrator(factory, settings, worker.artifacts, library)
    _, run = orchestrator.create_project(
        ProjectCreate(
            name="Selfcheck",
            idea="System testowy analizujący pomysł i tworzący architekturę oraz backlog.",
            models=["openai", "gemini", "deepseek"],
            scopes=["github", "reddit", "google", "web"],
            google_research_input="Google result https://example.org/google opis",
        )
    )
    safety = 0
    while safety < 200:
        safety += 1
        worked = await worker.run_once()
        with factory() as session:
            state = session.scalar(select(Run.status).where(Run.id == run.id))
        if state in {"COMPLETE", "PARTIAL"}:
            break
        if not worked:
            orchestrator.advance(run.id)
            await asyncio.sleep(0)
    with factory() as session:
        final = session.get(Run, run.id)
        if final.status != "COMPLETE":
            raise AssertionError(f"Selfcheck zakończył się statusem {final.status}")
    reports = list((root / "artifacts").rglob("report.md"))
    if len(reports) != 1 or reports[0].stat().st_size < 1000:
        raise AssertionError("Nie powstał kompletny raport Markdown")
    for name in ("user_stories.md", "specification.feature", "project_structure.md", "coding_prompt.md"):
        if not (reports[0].parent / name).is_file():
            raise AssertionError(f"Nie powstał wymagany artefakt: {name}")
    return reports[0]


def main() -> None:
    report = asyncio.run(run_selfcheck())
    print(f"SELFCHECK OK: {report}")


if __name__ == "__main__":
    main()
