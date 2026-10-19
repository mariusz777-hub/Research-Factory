from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined


@dataclass(frozen=True)
class RenderedQuestion:
    template_id: str
    category: str
    ordinal: int
    prompt: str
    checksum: str


@dataclass(frozen=True)
class QuestionLibrary:
    version: str
    language: str
    system_prompt: str
    questions: list[dict]

    def render(self, *, project_name: str, idea: str) -> list[RenderedQuestion]:
        env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
        rendered: list[RenderedQuestion] = []
        seen: set[str] = set()
        ordinal = 0
        for raw in self.questions:
            if not raw.get("enabled", True):
                continue
            template_id = str(raw.get("id", "")).strip()
            template = str(raw.get("template", "")).strip()
            category = str(raw.get("category", "general")).strip() or "general"
            if not template_id or not template:
                raise ValueError("Każde aktywne pytanie wymaga pól id i template")
            if template_id in seen:
                raise ValueError(f"Powtórzone id pytania: {template_id}")
            seen.add(template_id)
            ordinal += 1
            prompt = env.from_string(template).render(project_name=project_name, idea=idea).strip()
            checksum = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            rendered.append(RenderedQuestion(template_id, category, ordinal, prompt, checksum))
        if not rendered:
            raise ValueError("Biblioteka pytań nie zawiera aktywnych pytań")
        return rendered


def load_question_library(path: str | Path) -> QuestionLibrary:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Brak biblioteki pytań: {file_path}")
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("question_templates.yaml wymaga listy questions")
    system_prompt = str(data.get("system_prompt", "")).strip()
    if not system_prompt:
        raise ValueError("question_templates.yaml wymaga system_prompt")
    return QuestionLibrary(
        version=str(data.get("version", "1")),
        language=str(data.get("language", "pl")),
        system_prompt=system_prompt,
        questions=questions,
    )
