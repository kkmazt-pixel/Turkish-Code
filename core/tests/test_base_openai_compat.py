"""Tests for the shared OpenAI-compatible adapter (doc 22 §7) via a real
httpx client wired to a mock transport — real request-building/parsing
logic, substituted network layer (no real API key/network call)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError
from turkish_code.saglayicilar.base_openai_compat import BaseOpenAICompatProvider
from turkish_code.saglayicilar.provider import (
    RATE_LIMIT_CODE,
    ChatMessage,
    HealthStatus,
)
from turkish_code.saglayicilar.seeds import default_seed
from turkish_code.yonlendirme.capability import Role

BASE_URL = "https://api.example.test/v1"


Handler = Callable[[httpx.Request], httpx.Response]


def _provider(
    handler: Handler, *, api_key: str | None = "secret-key"
) -> BaseOpenAICompatProvider:
    from turkish_code.saglayicilar.provider import TierInfo

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BaseOpenAICompatProvider(
        "groq",
        base_url=BASE_URL,
        api_key=api_key,
        tier_info=TierInfo(tier="free", quota_limits={}),
        model_seeds={"llama": default_seed(Role.CHAT)},
        client=client,
    )


@pytest.mark.asyncio
async def test_list_models_parses_response_and_seeds_unknown_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-key"
        return httpx.Response(200, json={"data": [{"id": "llama"}, {"id": "mystery"}]})

    models = await _provider(handler).list_models()
    assert [m.id for m in models] == ["llama", "mystery"]
    assert models[1].capabilities == default_seed().capabilities  # unseeded fallback


@pytest.mark.asyncio
async def test_chat_streams_and_parses_sse_with_usage() -> None:
    sse_body = (
        'data: {"choices":[{"delta":{"content":"Mer"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{"content":"haba"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
        '"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        return httpx.Response(
            200, content=sse_body, headers={"content-type": "text/event-stream"}
        )

    provider = _provider(handler)
    chunks = [
        chunk
        async for chunk in provider.chat(
            "llama", [ChatMessage(role="user", content="hi")]
        )
    ]

    assert "".join(c.delta for c in chunks) == "Merhaba"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.prompt_tokens == 5


@pytest.mark.asyncio
async def test_rate_limit_maps_to_typed_retryable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    with pytest.raises(AppError) as excinfo:
        await _provider(handler).list_models()
    assert excinfo.value.code == RATE_LIMIT_CODE
    assert excinfo.value.retryable is True


@pytest.mark.asyncio
async def test_server_error_maps_to_retryable_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(AppError) as excinfo:
        await _provider(handler).list_models()
    assert excinfo.value.code == "provider.http_error"
    assert excinfo.value.retryable is True


@pytest.mark.asyncio
async def test_client_error_maps_to_non_retryable_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    with pytest.raises(AppError) as excinfo:
        await _provider(handler).list_models()
    assert excinfo.value.retryable is False


@pytest.mark.asyncio
async def test_embed_parses_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    vectors = await _provider(handler).embed("llama", ["hi"], EmbeddingKind.DOCUMENT)
    assert vectors == [[0.1, 0.2]]


@pytest.mark.asyncio
async def test_rerank_is_unsupported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("rerank should never hit the network")

    with pytest.raises(AppError) as excinfo:
        await _provider(handler).rerank("llama", "q", ["a", "b"])
    assert excinfo.value.code == "provider.capability_unsupported"


@pytest.mark.asyncio
async def test_health_up_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    assert await _provider(handler).health() is HealthStatus.UP


@pytest.mark.asyncio
async def test_health_cooling_down_on_429() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    assert await _provider(handler).health() is HealthStatus.COOLING_DOWN


@pytest.mark.asyncio
async def test_health_down_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    assert await _provider(handler).health() is HealthStatus.DOWN


def test_no_api_key_omits_authorization_header() -> None:
    provider = _provider(lambda request: httpx.Response(200), api_key=None)
    assert "Authorization" not in provider._headers()
