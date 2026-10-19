from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .settings import Settings


class GatewayError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    content: str
    raw: dict[str, Any]
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)


class AsyncSpacingLimiter:
    """Minimalny odstęp per provider; retry jest planowany przez kolejkę, nie przez sleep."""

    def __init__(self, seconds: float):
        self.seconds = max(0.0, seconds)
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_started: dict[str, float] = {}

    async def wait(self, key: str) -> None:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            elapsed = time.monotonic() - self._last_started.get(key, 0.0)
            remaining = self.seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_started[key] = time.monotonic()


def _http_error(response: httpx.Response, provider: str) -> GatewayError:
    retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
    body = response.text[:1000]
    return GatewayError(
        f"{provider} HTTP {response.status_code}: {body}",
        retryable=retryable,
    )


class ChatCompletionsAdapter:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        client: httpx.AsyncClient | None = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = client

    async def complete(self, prompt: str, system_prompt: str) -> ModelResult:
        if not self.api_key:
            raise GatewayError(f"Brak klucza API dla {self.provider}", retryable=False)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        started = time.perf_counter()
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if response.is_error:
                raise _http_error(response, self.provider)
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise GatewayError(f"Nieprawidłowa odpowiedź {self.provider}: {data}") from exc
            if not str(content).strip():
                raise GatewayError(f"{self.provider} zwrócił pustą odpowiedź")
            return ModelResult(
                provider=self.provider,
                model=self.model,
                content=str(content).strip(),
                raw=data,
                latency_ms=int((time.perf_counter() - started) * 1000),
                usage={
                    "input_tokens": int((data.get("usage") or {}).get("prompt_tokens", 0) or 0),
                    "output_tokens": int((data.get("usage") or {}).get("completion_tokens", 0) or 0),
                    "total_tokens": int((data.get("usage") or {}).get("total_tokens", 0) or 0),
                },
            )
        except httpx.TimeoutException as exc:
            raise GatewayError(f"Timeout {self.provider}: {exc}") from exc
        except httpx.RequestError as exc:
            raise GatewayError(f"Błąd sieci {self.provider}: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()


class GeminiAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        client: httpx.AsyncClient | None = None,
    ):
        self.provider = "gemini"
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = client

    async def complete(self, prompt: str, system_prompt: str) -> ModelResult:
        if not self.api_key:
            raise GatewayError("Brak klucza API dla gemini", retryable=False)
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        started = time.perf_counter()
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            if response.is_error:
                raise _http_error(response, self.provider)
            data = response.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
                content = "\n".join(str(part.get("text", "")) for part in parts).strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise GatewayError(f"Nieprawidłowa odpowiedź gemini: {data}") from exc
            if not content:
                reason = data.get("promptFeedback", {})
                raise GatewayError(f"Gemini zwrócił pustą odpowiedź: {reason}", retryable=False)
            return ModelResult(
                provider=self.provider,
                model=self.model,
                content=content,
                raw=data,
                latency_ms=int((time.perf_counter() - started) * 1000),
                usage={
                    "input_tokens": int((data.get("usageMetadata") or {}).get("promptTokenCount", 0) or 0),
                    "output_tokens": int((data.get("usageMetadata") or {}).get("candidatesTokenCount", 0) or 0),
                    "total_tokens": int((data.get("usageMetadata") or {}).get("totalTokenCount", 0) or 0),
                },
            )
        except httpx.TimeoutException as exc:
            raise GatewayError(f"Timeout gemini: {exc}") from exc
        except httpx.RequestError as exc:
            raise GatewayError(f"Błąd sieci gemini: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()


class ModelGateway:
    def __init__(self, settings: Settings, *, clients: dict[str, httpx.AsyncClient] | None = None):
        clients = clients or {}
        self.settings = settings
        self.limiter = AsyncSpacingLimiter(settings.model_min_interval_seconds)
        self.adapters = {
            "openai": ChatCompletionsAdapter(
                provider="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                timeout=settings.model_timeout_seconds,
                client=clients.get("openai"),
            ),
            "deepseek": ChatCompletionsAdapter(
                provider="deepseek",
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                timeout=settings.model_timeout_seconds,
                client=clients.get("deepseek"),
            ),
            "gemini": GeminiAdapter(
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
                model=settings.gemini_model,
                timeout=settings.model_timeout_seconds,
                client=clients.get("gemini"),
            ),
        }

    async def complete(self, model_name: str, prompt: str, system_prompt: str) -> ModelResult:
        adapter = self.adapters.get(model_name)
        if adapter is None:
            raise GatewayError(f"Nieznany adapter modelu: {model_name}", retryable=False)
        await self.limiter.wait(model_name)
        return await adapter.complete(prompt, system_prompt)
