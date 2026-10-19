from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..artifacts import ArtifactStore
from ..db import SessionLocal, init_db
from ..models import Event, Job, Project, Question, Run
from ..orchestrator import Orchestrator
from ..question_library import load_question_library
from ..schemas import ProjectCreate
from ..settings import get_settings

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))
STAGE_ORDER = [
    "MODEL_ANSWER",
    "GITHUB_RESEARCH",
    "REDDIT_RESEARCH",
    "GOOGLE_RESEARCH",
    "WEB_RESEARCH",
    "COMPARE",
    "SYNTHESIS",
    "REPORT",
]
STAGE_LABELS = {
    "MODEL_ANSWER": "Odpowiedzi modeli",
    "GITHUB_RESEARCH": "Research GitHub",
    "REDDIT_RESEARCH": "Research Reddit",
    "GOOGLE_RESEARCH": "Research Google",
    "WEB_RESEARCH": "Research WWW",
    "COMPARE": "Porównanie modeli",
    "SYNTHESIS": "Specyfikacja badanego projektu",
    "REPORT": "Raport Markdown",
}


def _services():
    settings = get_settings()
    artifacts = ArtifactStore(settings.artifact_root)
    library = load_question_library(settings.question_library)
    orchestrator = Orchestrator(SessionLocal, settings, artifacts, library)
    return settings, artifacts, library, orchestrator


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Research Factory", version="1.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="static")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        with SessionLocal() as session:
            projects = list(
                session.scalars(
                    select(Project)
                    .options(selectinload(Project.runs))
                    .order_by(Project.created_at.desc())
                    .limit(30)
                )
            )
        return TEMPLATES.TemplateResponse(request, "index.html", {"projects": projects, "error": ""})

    @app.post("/projects")
    def create_project(
        request: Request,
        name: str = Form(...),
        idea: str = Form(...),
        google_research_input: str = Form(default=""),
        models: list[str] = Form(...),
        scopes: list[str] = Form(default=[]),
    ):
        _, _, _, orchestrator = _services()
        try:
            payload = ProjectCreate(
                name=name,
                idea=idea,
                models=models,
                scopes=scopes,
                google_research_input=google_research_input,
            )
            project, run = orchestrator.create_project(payload)
        except (ValidationError, ValueError, FileNotFoundError) as exc:
            with SessionLocal() as session:
                projects = list(
                    session.scalars(
                        select(Project)
                        .options(selectinload(Project.runs))
                        .order_by(Project.created_at.desc())
                        .limit(30)
                    )
                )
            return TEMPLATES.TemplateResponse(
                request,
                "index.html",
                {
                    "projects": projects,
                    "error": str(exc),
                    "form": {
                        "name": name,
                        "idea": idea,
                        "google_research_input": google_research_input,
                    },
                },
                status_code=422,
            )
        return RedirectResponse(url=f"/projects/{project.id}/runs/{run.id}", status_code=303)

    @app.get("/projects/{project_id}/runs/{run_id}", response_class=HTMLResponse)
    def project_status(request: Request, project_id: str, run_id: str):
        with SessionLocal() as session:
            project = session.get(Project, project_id)
            run = session.get(Run, run_id)
            if project is None or run is None or run.project_id != project.id:
                raise HTTPException(status_code=404, detail="Nie znaleziono projektu")
        return TEMPLATES.TemplateResponse(
            request,
            "project.html",
            {"project": project, "run": run, "stage_labels": STAGE_LABELS},
        )

    @app.get("/api/runs/{run_id}/status")
    def run_status(run_id: str):
        with SessionLocal() as session:
            run = session.get(Run, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Nie znaleziono runu")
            project = session.get(Project, run.project_id)
            jobs = list(session.scalars(select(Job).where(Job.run_id == run_id).order_by(Job.created_at)))
            events = list(
                session.scalars(
                    select(Event).where(Event.run_id == run_id).order_by(Event.created_at.desc()).limit(25)
                )
            )
            question_count = len(list(session.scalars(select(Question.id).where(Question.run_id == run_id))))

        grouped: dict[str, Counter] = defaultdict(Counter)
        for job in jobs:
            grouped[job.job_type][job.status] += 1
        stages = []
        for stage in STAGE_ORDER:
            counts = grouped.get(stage, Counter())
            total = sum(counts.values())
            if total == 0:
                scope_by_stage = {
                    "GITHUB_RESEARCH": "github",
                    "REDDIT_RESEARCH": "reddit",
                    "GOOGLE_RESEARCH": "google",
                    "WEB_RESEARCH": "web",
                }
                required_scope = scope_by_stage.get(stage)
                if required_scope and required_scope not in project.selected_scopes:
                    state = "SKIPPED"
                else:
                    state = "PENDING"
            elif counts["FAILED"] and counts["SUCCESS"] + counts["FAILED"] == total:
                state = "PARTIAL"
            elif counts["SUCCESS"] == total:
                state = "SUCCESS"
            elif counts["RUNNING"]:
                state = "RUNNING"
            elif counts["RETRY"]:
                state = "RETRY"
            else:
                state = "QUEUED"
            stages.append({"key": stage, "label": STAGE_LABELS[stage], "state": state, "counts": dict(counts), "total": total})
        terminal = sum(job.status in {"SUCCESS", "FAILED"} for job in jobs)
        progress = round(100 * terminal / len(jobs), 1) if jobs else 0
        artifact_paths = {job.result_path for job in jobs if job.result_path}
        _, artifact_store, _, _ = _services()
        base = artifact_store.run_root(project.slug, run_id).relative_to(artifact_store.root)
        for relative in (
            base / "manifest.json",
            base / "artifact_manifest.json",
            base / "reports" / "report.md",
            base / "reports" / "architecture.md",
            base / "reports" / "backlog.md",
            base / "reports" / "user_stories.md",
            base / "reports" / "specification.feature",
            base / "reports" / "project_structure.md",
            base / "reports" / "coding_prompt.md",
            base / "reports" / "executive_summary.md",
            base / "logs" / "events.jsonl",
        ):
            if artifact_store.resolve_public(relative.as_posix()).is_file():
                artifact_paths.add(relative.as_posix())
        artifact_paths = sorted(artifact_paths)
        return {
            "project": {"id": project.id, "name": project.name, "status": project.status},
            "run": {"id": run.id, "status": run.status, "progress": progress},
            "question_count": question_count,
            "job_count": len(jobs),
            "terminal_count": terminal,
            "stages": stages,
            "artifacts": [{"name": Path(path).name, "path": path, "url": f"/artifacts/{path}"} for path in artifact_paths],
            "events": [
                {"at": event.created_at.isoformat(), "level": event.level, "type": event.event_type, "message": event.message}
                for event in events
            ],
        }

    @app.get("/artifacts/{relative_path:path}")
    def download_artifact(relative_path: str):
        _, artifacts, _, _ = _services()
        try:
            path = artifacts.resolve_public(relative_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Nieprawidłowa ścieżka") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Brak artefaktu")
        return FileResponse(path, filename=path.name)

    return app


def main() -> None:
    uvicorn.run("research_factory.api.app:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
