from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .google_scraper_adapter import GoogleScraperAdapter
from .settings import Settings


class ResearchError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class Source:
    source_type: str
    title: str
    url: str
    snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    verification_status: str = "UNVERIFIED"


class GitHubResearch:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def search(self, query: str) -> list[Source]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "research-factory/1.0",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.settings.research_timeout_seconds)
        try:
            response = await client.get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": self.settings.github_result_limit,
                },
            )
            if response.status_code == 403 and not self.settings.github_token:
                raise ResearchError("Limit anonimowego GitHub API; ustaw GITHUB_TOKEN")
            if response.is_error:
                retryable = response.status_code == 429 or response.status_code >= 500
                raise ResearchError(
                    f"GitHub HTTP {response.status_code}: {response.text[:700]}",
                    retryable=retryable,
                )
            result = []
            for item in response.json().get("items", []):
                result.append(
                    Source(
                        source_type="github",
                        title=item.get("full_name", "repozytorium"),
                        url=item.get("html_url", ""),
                        snippet=item.get("description") or "",
                        metadata={
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language"),
                            "license": (item.get("license") or {}).get("spdx_id"),
                            "updated_at": item.get("updated_at"),
                            "topics": item.get("topics", []),
                            "token_used": bool(self.settings.github_token),
                        },
                    )
                )
            return [item for item in result if item.url]
        except httpx.TimeoutException as exc:
            raise ResearchError(f"Timeout GitHub: {exc}") from exc
        except httpx.RequestError as exc:
            raise ResearchError(f"Błąd sieci GitHub: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()


class RedditResearch:
    """Wyszukiwanie Reddit z opcjonalnym tokenem OAuth.

    Token jest przekazywany wyłącznie w nagłówku i nie trafia do źródeł,
    artefaktów ani treści błędu.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def search(self, query: str) -> list[Source]:
        token = self.settings.reddit_token.strip()
        endpoint = (
            "https://oauth.reddit.com/search"
            if token
            else "https://www.reddit.com/search.json"
        )
        headers = {
            "User-Agent": self.settings.reddit_user_agent,
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.settings.research_timeout_seconds)
        try:
            response = await client.get(
                endpoint,
                headers=headers,
                params={
                    "q": query,
                    "limit": self.settings.reddit_result_limit,
                    "sort": "relevance",
                    "type": "link",
                    "raw_json": 1,
                },
            )
            if response.is_error:
                retryable = response.status_code == 429 or response.status_code >= 500
                raise ResearchError(
                    f"Reddit HTTP {response.status_code}",
                    retryable=retryable,
                )
            children = ((response.json().get("data") or {}).get("children") or [])
            sources: list[Source] = []
            for child in children[: self.settings.reddit_result_limit]:
                item = child.get("data") or {}
                permalink = str(item.get("permalink") or "")
                url = (
                    f"https://www.reddit.com{permalink}"
                    if permalink.startswith("/")
                    else str(item.get("url") or "")
                )
                if not url:
                    continue
                sources.append(
                    Source(
                        source_type="reddit",
                        title=str(item.get("title") or "Post Reddit"),
                        url=url,
                        snippet=str(item.get("selftext") or "")[:5000],
                        metadata={
                            "provider": "reddit-oauth" if token else "reddit-public",
                            "subreddit": item.get("subreddit"),
                            "author": item.get("author"),
                            "score": item.get("score", 0),
                            "num_comments": item.get("num_comments", 0),
                            "created_utc": item.get("created_utc"),
                            "external_url": item.get("url_overridden_by_dest") or item.get("url"),
                            "token_used": bool(token),
                        },
                    )
                )
            return sources
        except httpx.TimeoutException as exc:
            raise ResearchError("Timeout Reddit") from exc
        except httpx.RequestError as exc:
            raise ResearchError(f"Błąd sieci Reddit: {type(exc).__name__}") from exc
        finally:
            if owns_client:
                await client.aclose()


_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_URL = re.compile(r"https?://[^\s)>\]}]+")


def parse_google_research_input(text: str, limit: int) -> list[Source]:
    """Normalizuje wklejony research Google bez nowej biblioteki pytań."""
    value = (text or "").strip()
    if not value:
        return []
    items: list[dict[str, Any]] = []
    if value[:1] in "[{":
        try:
            payload = json.loads(value)
            if isinstance(payload, dict):
                payload = payload.get("results") or payload.get("items") or []
            if isinstance(payload, list):
                for raw in payload:
                    if isinstance(raw, dict):
                        items.append(raw)
        except json.JSONDecodeError:
            items = []
    if not items:
        for line in value.splitlines():
            markdown = _MARKDOWN_LINK.search(line)
            if markdown:
                items.append(
                    {
                        "title": markdown.group(1),
                        "url": markdown.group(2),
                        "snippet": line[markdown.end() :].strip(" -—:[]"),
                    }
                )
                continue
            match = _URL.search(line)
            if match:
                items.append(
                    {
                        "title": line[: match.start()].strip(" #*-[]") or match.group(0),
                        "url": match.group(0).rstrip(".,;:"),
                        "snippet": line[match.end() :].strip(" -—:[]"),
                    }
                )
    output: list[Source] = []
    seen: set[str] = set()
    for item in items:
        url = str(item.get("url") or item.get("link") or "").strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        output.append(
            Source(
                source_type="google",
                title=str(item.get("title") or url).strip(),
                url=url,
                snippet=str(item.get("snippet") or item.get("description") or "").strip(),
                metadata={"provider": "google-input", "input": True},
                verification_status="INPUT",
            )
        )
        if len(output) >= limit:
            break
    return output


class GoogleResearch:
    """Łączy research wejściowy z adapterem istniejącego scrapera użytkownika."""

    def __init__(
        self,
        settings: Settings,
        adapter: GoogleScraperAdapter | None = None,
    ):
        self.settings = settings
        self.adapter = adapter or GoogleScraperAdapter(
            settings.google_scraper_target,
            settings.google_result_limit,
        )

    async def search(self, query: str, input_text: str = "") -> list[Source]:
        sources = parse_google_research_input(input_text, self.settings.google_result_limit)
        if self.adapter.configured:
            try:
                scraped = await self.adapter.search(query)
            except Exception as exc:
                if not sources:
                    raise ResearchError(
                        f"Adapter scrapera Google: {type(exc).__name__}: {exc}",
                        retryable=False,
                    ) from exc
                sources[0].metadata["scraper_error"] = f"{type(exc).__name__}: {exc}"
            else:
                sources.extend(
                    Source(
                        source_type="google",
                        title=item.title,
                        url=item.url,
                        snippet=item.snippet,
                        metadata={"provider": "user-google-scraper", **(item.metadata or {})},
                    )
                    for item in scraped
                )
        elif not sources:
            raise ResearchError(
                "Brak wejściowego researchu Google i GOOGLE_SCRAPER_TARGET",
                retryable=False,
            )
        deduped: list[Source] = []
        seen: set[str] = set()
        for source in sources:
            if source.url in seen:
                continue
            seen.add(source.url)
            deduped.append(source)
        return deduped[: self.settings.google_result_limit]


class WebResearch:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def search(self, query: str) -> list[Source]:
        if self.settings.tavily_api_key:
            return await self._tavily(query)
        return await self._duckduckgo(query)

    async def _tavily(self, query: str) -> list[Source]:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.settings.research_timeout_seconds)
        try:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.settings.tavily_api_key,
                    "query": query,
                    "max_results": self.settings.web_result_limit,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
            if response.is_error:
                raise ResearchError(
                    f"Tavily HTTP {response.status_code}: {response.text[:700]}",
                    retryable=response.status_code == 429 or response.status_code >= 500,
                )
            return [
                Source(
                    source_type="web",
                    title=item.get("title", "wynik WWW"),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    metadata={"score": item.get("score"), "provider": "tavily"},
                )
                for item in response.json().get("results", [])
                if item.get("url")
            ]
        except httpx.TimeoutException as exc:
            raise ResearchError(f"Timeout Tavily: {exc}") from exc
        except httpx.RequestError as exc:
            raise ResearchError(f"Błąd sieci Tavily: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def _duckduckgo(self, query: str) -> list[Source]:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.settings.research_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchFactory/1.0)"},
        )
        try:
            response = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
            if response.is_error:
                raise ResearchError(
                    f"DuckDuckGo HTTP {response.status_code}: {response.text[:500]}",
                    retryable=response.status_code == 429 or response.status_code >= 500,
                )
            soup = BeautifulSoup(response.text, "html.parser")
            sources: list[Source] = []
            for result in soup.select(".result"):
                link = result.select_one("a.result__a")
                if link is None:
                    continue
                href = str(link.get("href", ""))
                parsed = urlparse(href)
                if "duckduckgo.com" in parsed.netloc:
                    href = unquote(parse_qs(parsed.query).get("uddg", [href])[0])
                snippet_node = result.select_one(".result__snippet")
                sources.append(
                    Source(
                        source_type="web",
                        title=link.get_text(" ", strip=True),
                        url=href,
                        snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                        metadata={"provider": "duckduckgo-html"},
                    )
                )
                if len(sources) >= self.settings.web_result_limit:
                    break
            if not sources:
                raise ResearchError("Wyszukiwarka WWW nie zwróciła wyników")
            return sources
        except httpx.TimeoutException as exc:
            raise ResearchError(f"Timeout DuckDuckGo: {exc}") from exc
        except httpx.RequestError as exc:
            raise ResearchError(f"Błąd sieci DuckDuckGo: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
