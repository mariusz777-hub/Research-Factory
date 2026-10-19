"""Offline contract check for the in-place update; does not require a database."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from research_factory.google_scraper_adapter import GoogleScraperAdapter
from research_factory.question_library import load_question_library
from research_factory.research import GoogleResearch, parse_google_research_input
from research_factory.settings import Settings
from research_factory.synthesis_contract import synthesis_errors, synthesis_outputs

EXPECTED_QUESTION_SHA256 = "5ee022bd6ffae27a0ff850c01b8315c271a6d59ec6d038b81ee34f943a6082ac"


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    questions = root / "config" / "question_templates.yaml"
    digest = hashlib.sha256(questions.read_bytes()).hexdigest()
    assert digest == EXPECTED_QUESTION_SHA256, "Zmieniono bazowy question_templates.yaml"
    library = load_question_library(questions)
    rendered = library.render(project_name="Kontrola", idea="Opis pomysłu do kontroli regresji.")
    assert len(rendered) == 12
    html = (root / "src/research_factory/templates/index.html").read_text(encoding="utf-8")
    assert "question_templates" not in html and "system_architecture" not in html
    for required in (
        'name="name"', 'name="idea"', 'value="openai"', 'value="gemini"',
        'value="deepseek"', 'value="github"', 'value="web"', 'value="reddit"',
        'value="google"', 'name="google_research_input"',
    ):
        assert required in html, f"Brak zachowanego/dodanego pola GUI: {required}"
    parsed = parse_google_research_input("Źródło https://example.org opis", 10)
    assert len(parsed) == 1 and parsed[0].url == "https://example.org"

    async def scraper(query, limit):
        return [{"title": query, "url": "https://example.org/scraper", "snippet": "wynik"}]

    adapter = GoogleScraperAdapter("", 5, scraper=scraper)
    settings = Settings(google_result_limit=5)
    sources = await GoogleResearch(settings, adapter).search(
        "kontrola", "Input https://example.org/input opis"
    )
    assert {item.url for item in sources} == {
        "https://example.org/input", "https://example.org/scraper"
    }
    synthesis = {
        "executive_summary": "x" * 20,
        "architecture_markdown": "a" * 100,
        "backlog_markdown": "b" * 100,
        "user_stories_markdown": "u" * 100,
        "gherkin_feature": "Funkcja: X\nScenariusz: Y\n" + "g" * 150,
        "project_structure_markdown": "p" * 100,
        "coding_prompt_markdown": "c" * 150,
    }
    assert synthesis_errors(synthesis) == []
    assert set(synthesis_outputs(synthesis)) >= {
        "architecture.md", "user_stories.md", "specification.feature",
        "project_structure.md", "coding_prompt.md",
    }
    print("IN-PLACE UPDATE CONTRACT: OK — 12 pytań, GUI bez szablonów, Google input + adapter")


if __name__ == "__main__":
    asyncio.run(main())
