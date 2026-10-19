"""Adapter do istniejącego lokalnego scrapera Google użytkownika.

Adapter nie zastępuje scrapera i nie zmienia jego kodu. Ładuje wskazaną funkcję
z modułu lub pliku .py i normalizuje jej wynik do stabilnego kontraktu Factory.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


@dataclass(frozen=True)
class GoogleScraperResult:
    title: str
    url: str
    snippet: str = ""
    metadata: dict[str, Any] | None = None


def _load_module(location: str) -> ModuleType:
    candidate = Path(location).expanduser()
    if candidate.suffix.lower() == ".py" or candidate.is_file():
        if not candidate.is_file():
            raise FileNotFoundError(f"Brak pliku scrapera Google: {candidate}")
        spec = importlib.util.spec_from_file_location("research_factory_user_google_scraper", candidate)
        if spec is None or spec.loader is None:
            raise ImportError(f"Nie można załadować scrapera Google: {candidate}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(location)


def load_scraper(target: str) -> Callable[..., Any]:
    location, separator, callable_name = target.strip().rpartition(":")
    if not separator or not location or not callable_name:
        raise ValueError(
            "GOOGLE_SCRAPER_TARGET musi mieć format module:function albo C:/plik.py:function"
        )
    module = _load_module(location)
    scraper = getattr(module, callable_name, None)
    if not callable(scraper):
        raise AttributeError(f"Brak funkcji {callable_name!r} w {location!r}")
    return scraper


def _field(item: Any, *names: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        for name in names:
            value = item.get(name)
            if value not in (None, ""):
                return value
        return default
    for name in names:
        value = getattr(item, name, None)
        if value not in (None, ""):
            return value
    return default


def normalize_results(payload: Any, limit: int) -> list[GoogleScraperResult]:
    if isinstance(payload, dict):
        payload = payload.get("results") or payload.get("items") or payload.get("organic") or []
    if payload is None:
        payload = []
    if isinstance(payload, (str, bytes)):
        payload = [payload]
    results: list[GoogleScraperResult] = []
    for item in list(payload)[:limit]:
        if isinstance(item, str):
            url, title, snippet, metadata = item.strip(), item.strip(), "", {}
        else:
            url = str(_field(item, "url", "link", "href")).strip()
            title = str(_field(item, "title", "name", default=url)).strip()
            snippet = str(_field(item, "snippet", "description", "text", "content")).strip()
            metadata = _field(item, "metadata", default={})
            if not isinstance(metadata, dict):
                metadata = {"scraper_metadata": str(metadata)}
        if not url.startswith(("http://", "https://")):
            continue
        results.append(GoogleScraperResult(title or url, url, snippet, metadata or {}))
    return results


class GoogleScraperAdapter:
    def __init__(self, target: str, limit: int, scraper: Callable[..., Any] | None = None):
        self.target = target.strip()
        self.limit = limit
        self.scraper = scraper

    @property
    def configured(self) -> bool:
        return self.scraper is not None or bool(self.target)

    async def search(self, query: str) -> list[GoogleScraperResult]:
        scraper = self.scraper or load_scraper(self.target)
        signature = inspect.signature(scraper)
        candidates = [
            ((), {"query": query, "limit": self.limit}),
            ((query, self.limit), {}),
            ((query,), {}),
        ]
        call = None
        for args, kwargs in candidates:
            try:
                signature.bind(*args, **kwargs)
            except TypeError:
                continue
            call = (args, kwargs)
            break
        if call is None:
            raise TypeError(
                "Funkcja scrapera Google musi przyjmować query oraz opcjonalnie limit"
            )
        value = scraper(*call[0], **call[1])
        if inspect.isawaitable(value):
            value = await value
        return normalize_results(value, self.limit)
