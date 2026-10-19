import httpx
import pytest

from research_factory.model_gateway import ChatCompletionsAdapter, GeminiAdapter, GatewayError


@pytest.mark.asyncio
async def test_openai_compatible_adapter_parses_content():
    async def handler(request: httpx.Request):
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "gotowe"}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ChatCompletionsAdapter(
        provider="openai", api_key="secret", base_url="https://api.test/v1",
        model="model-x", timeout=5, client=client,
    )
    result = await adapter.complete("pytanie", "system")
    assert result.content == "gotowe"
    assert result.model == "model-x"
    assert result.usage["total_tokens"] == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_deepseek_uses_openai_compatible_contract():
    async def handler(request: httpx.Request):
        assert request.url == "https://api.deepseek.test/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "deep"}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ChatCompletionsAdapter(
        provider="deepseek", api_key="secret", base_url="https://api.deepseek.test",
        model="deepseek-chat", timeout=5, client=client,
    )
    result = await adapter.complete("pytanie", "system")
    assert result.provider == "deepseek" and result.content == "deep"
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_adapter_parses_parts():
    async def handler(request: httpx.Request):
        assert request.url.params["key"] == "gem-key"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "A"}, {"text": "B"}]}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiAdapter(api_key="gem-key", base_url="https://gem.test/v1beta", model="gem", timeout=5, client=client)
    result = await adapter.complete("p", "s")
    assert result.content == "A\nB"
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_key_is_non_retryable():
    adapter = ChatCompletionsAdapter(provider="deepseek", api_key="", base_url="https://x", model="m", timeout=5)
    with pytest.raises(GatewayError) as error:
        await adapter.complete("p", "s")
    assert error.value.retryable is False
