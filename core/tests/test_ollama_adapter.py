"""Tests for the Ollama adapter's native wire format (doc 22 §5.5)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError
from turkish_code.saglayicilar.ollama.adapter import OllamaProvider
from turkish_code.saglayicilar.provider import ChatMessage, HealthStatus, ProviderKind
from turkish_code.saglayicilar.seeds import default_seed
from turkish_code.yonlendirme.capability import Role

BASE_URL = "http://localhost:11434"
Handler = Callable[[httpx.Request], httpx.Response]


def _provider(handler: Handler) -> OllamaProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaProvider(
        base_url=BASE_URL,
        model_seeds={"llama3": default_seed(Role.CHAT)},
        client=client,
    )


def test_kind_is_local_and_is_offline_fallback() -> None:
    provider = _provider(lambda r: httpx.Response(200))
    assert provider.kind is ProviderKind.LOCAL
    assert provider.is_offline_fallback is True


@pytest.mark.asyncio
async def test_list_models_parses_tags_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3"}]})

    models = await _provider(handler).list_models()
    assert models[0].id == "llama3"


@pytest.mark.asyncio
async def test_chat_streams_ndjson_and_final_usage() -> None:
    ndjson_body = (
        '{"message":{"role":"assistant","content":"Mer"},"done":false}\n'
        '{"message":{"role":"assistant","content":"haba"},"done":false}\n'
        '{"message":{"role":"assistant","content":""},"done":true,'
        '"prompt_eval_count":4,"eval_count":2}\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson_body)

    provider = _provider(handler)
    chunks = [
        chunk
        async for chunk in provider.chat(
            "llama3", [ChatMessage(role="user", content="hi")]
        )
    ]

    assert "".join(c.delta for c in chunks) == "Merhaba"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.completion_tokens == 2


@pytest.mark.asyncio
async def test_embed_calls_once_per_text() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"embedding": [0.1, 0.2]})

    vectors = await _provider(handler).embed(
        "llama3", ["a", "b"], EmbeddingKind.DOCUMENT
    )
    assert vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_rerank_is_unsupported() -> None:
    with pytest.raises(AppError) as excinfo:
        await _provider(lambda r: httpx.Response(200)).rerank("llama3", "q", ["a"])
    assert excinfo.value.code == "provider.capability_unsupported"


@pytest.mark.asyncio
async def test_health_down_when_daemon_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert await _provider(handler).health() is HealthStatus.DOWN


@pytest.mark.asyncio
async def test_health_up_on_200() -> None:
    assert await _provider(lambda r: httpx.Response(200)).health() is HealthStatus.UP
