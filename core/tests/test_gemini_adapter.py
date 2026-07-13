"""Tests for the Gemini adapter's Google GenAI wire format (doc 22 §5.1)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from turkish_code.hata import AppError
from turkish_code.saglayicilar.gemini.adapter import GeminiProvider
from turkish_code.saglayicilar.provider import (
    RATE_LIMIT_CODE,
    ChatMessage,
    HealthStatus,
    ProviderKind,
    TierInfo,
)
from turkish_code.saglayicilar.seeds import default_seed
from turkish_code.yonlendirme.capability import Role

BASE_URL = "https://generativelanguage.example.test"
Handler = Callable[[httpx.Request], httpx.Response]


def _provider(handler: Handler) -> GeminiProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GeminiProvider(
        base_url=BASE_URL,
        api_key="secret-key",
        tier_info=TierInfo(tier="free", quota_limits={}),
        model_seeds={"gemini-flash": default_seed(Role.CHAT)},
        client=client,
    )


def test_kind_is_cloud_and_not_offline_fallback() -> None:
    provider = _provider(lambda r: httpx.Response(200))
    assert provider.kind is ProviderKind.CLOUD
    assert provider.is_offline_fallback is False


@pytest.mark.asyncio
async def test_list_models_strips_models_prefix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "secret-key"
        return httpx.Response(200, json={"models": [{"name": "models/gemini-flash"}]})

    models = await _provider(handler).list_models()
    assert models[0].id == "gemini-flash"


@pytest.mark.asyncio
async def test_chat_maps_system_and_assistant_roles() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        sse_body = (
            'data: {"candidates":[{"content":{"parts":[{"text":"Merhaba"}]},'
            '"finishReason":null}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":""}]},'
            '"finishReason":"STOP"}],'
            '"usageMetadata":{"promptTokenCount":3,"candidatesTokenCount":1}}\n\n'
        )
        return httpx.Response(200, content=sse_body)

    provider = _provider(handler)
    messages = [
        ChatMessage(role="system", content="Sen yardımcısın."),
        ChatMessage(role="user", content="Merhaba"),
        ChatMessage(role="assistant", content="Selam"),
    ]
    chunks = [chunk async for chunk in provider.chat("gemini-flash", messages)]

    body = captured["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "Sen yardımcısın."
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "Merhaba"}]},
        {"role": "model", "parts": [{"text": "Selam"}]},
    ]
    assert chunks[0].delta == "Merhaba"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.prompt_tokens == 3


@pytest.mark.asyncio
async def test_rate_limit_maps_to_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    with pytest.raises(AppError) as excinfo:
        await _provider(handler).list_models()
    assert excinfo.value.code == RATE_LIMIT_CODE


@pytest.mark.asyncio
async def test_health_up_on_200() -> None:
    assert await _provider(lambda r: httpx.Response(200)).health() is HealthStatus.UP


@pytest.mark.asyncio
async def test_embed_parses_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": {"values": [0.5, 0.6]}})

    from turkish_code.gomme import EmbeddingKind

    vectors = await _provider(handler).embed(
        "gemini-flash", ["hi"], EmbeddingKind.DOCUMENT
    )
    assert vectors == [[0.5, 0.6]]
