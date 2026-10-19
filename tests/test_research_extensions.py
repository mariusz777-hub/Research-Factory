import asyncio
from pathlib import Path

import httpx

from research_factory.google_scraper_adapter import GoogleScraperAdapter, normalize_results
from research_factory.research import GoogleResearch, RedditResearch, parse_google_research_input
from research_factory.schemas import ProjectCreate
from research_factory.settings import Settings
from research_factory.synthesis_contract import synthesis_errors, synthesis_outputs


def test_existing_question_library_is_still_exactly_twelve_and_hidden(project_root, library):
    rendered = library.render(project_name="Projekt", idea="Opis pomysłu wystarczająco długi do testu.")
    assert len(rendered) == 12
    assert [item.template_id for item in rendered] == [
        "problem_value", "users_workflows", "market_alternatives", "functional_scope",
        "nonfunctional_requirements", "data_model", "system_architecture",
        "security_privacy", "integrations_limits", "testing_quality", "delivery_backlog",
        "operations_economics",
    ]
    html = (project_root / "src/research_factory/templates/index.html").read_text(encoding="utf-8")
    assert "question_templates" not in html
    assert "system_architecture" not in html


def test_project_schema_accepts_new_scopes_without_changing_models():
    value = ProjectCreate(
        name="Projekt",
        idea="Opis projektu mający więcej niż dwadzieścia znaków.",
        models=["openai", "gemini", "deepseek"],
        scopes=["github", "web", "reddit", "google"],
        google_research_input="Źródło https://example.org opis",
    )
    assert value.models == ["openai", "gemini", "deepseek"]
    assert value.scopes == ["github", "web", "reddit", "google"]


def test_google_input_is_normalized_without_replacing_question_library():
    sources = parse_google_research_input(
        "[Dokumentacja](https://example.org/docs) — opis\nRepo https://example.org/repo szczegóły",
        10,
    )
    assert [item.url for item in sources] == [
        "https://example.org/docs", "https://example.org/repo"
    ]
    assert all(item.source_type == "google" for item in sources)
    assert all(item.metadata["provider"] == "google-input" for item in sources)


def test_adapter_wraps_existing_google_scraper_callable():
    def existing_scraper(query, limit):
        return {"results": [{"title": query, "link": "https://example.org", "description": "opis"}]}

    adapter = GoogleScraperAdapter("", 5, scraper=existing_scraper)
    result = asyncio.run(adapter.search("projekt"))
    assert result[0].title == "projekt"
    assert result[0].url == "https://example.org"
    assert len(normalize_results(result, 5)) == 1


def test_google_input_works_without_configured_scraper():
    settings = Settings(google_scraper_target="", google_result_limit=5)
    sources = asyncio.run(
        GoogleResearch(settings).search("query", "Wynik https://example.org opis")
    )
    assert len(sources) == 1
    assert sources[0].verification_status == "INPUT"


def test_reddit_token_is_sent_only_in_authorization_header():
    seen = {}

    async def handler(request: httpx.Request):
        seen["authorization"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"data": {"children": [{"data": {
            "title": "Post", "permalink": "/r/test/comments/1/post", "author": "user",
            "subreddit": "test", "score": 7, "num_comments": 2,
        }}]}})

    async def execute():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            settings = Settings(reddit_token="SECRET", reddit_result_limit=5)
            return await RedditResearch(settings, client).search("query")
        finally:
            await client.aclose()

    sources = asyncio.run(execute())
    assert seen["authorization"] == "Bearer SECRET"
    assert "SECRET" not in seen["url"]
    assert sources[0].metadata["token_used"] is True


def test_synthesis_contract_rejects_factory_architecture_and_incomplete_gherkin():
    data = {
        "executive_summary": "x" * 20,
        "architecture_markdown": "Research Factory " + "a" * 100,
        "backlog_markdown": "b" * 100,
        "user_stories_markdown": "u" * 100,
        "gherkin_feature": "brak składni " + "g" * 150,
        "project_structure_markdown": "p" * 100,
        "coding_prompt_markdown": "c" * 150,
    }
    errors = synthesis_errors(data)
    assert any("miesza architekturę" in item for item in errors)
    assert any("Gherkin" in item for item in errors)


def test_synthesis_output_names_match_requested_project_artifacts():
    data = {
        "executive_summary": "summary",
        "architecture_markdown": "architecture",
        "backlog_markdown": "backlog",
        "user_stories_markdown": "stories",
        "gherkin_feature": "feature",
        "project_structure_markdown": "structure",
        "coding_prompt_markdown": "prompt",
    }
    assert set(synthesis_outputs(data)) == {
        "executive_summary.md", "architecture.md", "backlog.md", "user_stories.md",
        "specification.feature", "project_structure.md", "coding_prompt.md",
    }
