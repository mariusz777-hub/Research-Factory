"""Walidacja kompletności artefaktów badanego projektu, niezależna od kolejki i DB."""
from __future__ import annotations

from typing import Any

REQUIRED_SYNTHESIS_LENGTHS = {
    "executive_summary": 20,
    "architecture_markdown": 100,
    "backlog_markdown": 100,
    "user_stories_markdown": 100,
    "gherkin_feature": 150,
    "project_structure_markdown": 100,
    "coding_prompt_markdown": 150,
}

SYNTHESIS_OUTPUT_FILES = {
    "executive_summary.md": "executive_summary",
    "architecture.md": "architecture_markdown",
    "backlog.md": "backlog_markdown",
    "user_stories.md": "user_stories_markdown",
    "specification.feature": "gherkin_feature",
    "project_structure.md": "project_structure_markdown",
    "coding_prompt.md": "coding_prompt_markdown",
}


def synthesis_errors(data: dict[str, Any]) -> list[str]:
    errors = [
        f"brak lub zbyt krótki wynik: {key}"
        for key, minimum in REQUIRED_SYNTHESIS_LENGTHS.items()
        if len(str(data.get(key, "")).strip()) < minimum
    ]
    gherkin = str(data.get("gherkin_feature", ""))
    if gherkin and (
        not any(marker in gherkin for marker in ("Funkcja:", "Feature:"))
        or not any(marker in gherkin for marker in ("Scenariusz:", "Scenario:"))
    ):
        errors.append("niekompletna składnia Gherkin")
    for key in ("architecture_markdown", "project_structure_markdown"):
        if "research factory" in str(data.get(key, "")).casefold():
            errors.append(f"{key} miesza architekturę Factory z badanym projektem")
    return errors


def synthesis_outputs(data: dict[str, Any]) -> dict[str, str]:
    """Mapuje zatwierdzony JSON syntezy na stabilne nazwy plików raportu."""
    return {
        filename: str(data.get(key, "")).strip() + "\n"
        for filename, key in SYNTHESIS_OUTPUT_FILES.items()
    }
