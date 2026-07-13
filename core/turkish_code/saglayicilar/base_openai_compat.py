"""Shared adapter for OpenAI-compatible chat APIs (doc 22 §7).

Used by Groq, OpenRouter, and NVIDIA NIM's OpenAI-compatible endpoints —
one real HTTP implementation; each provider is a thin subclass supplying its
own ``base_url``/id/auth (ADR-0014, doc 22 §3 "no shared special-casing
leaking into the core" — the special-casing that *does* exist is confined to
this one shared, documented adapter, not scattered).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence

import httpx

from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError, ErrorKind
from turkish_code.saglayicilar.provider import (
    CAPABILITY_UNSUPPORTED_CODE,
    RATE_LIMIT_CODE,
    ChatChunk,
    ChatMessage,
    HealthStatus,
    ModelInfo,
    ProviderKind,
    RankedCandidate,
    TierInfo,
    Usage,
)
from turkish_code.saglayicilar.seeds import ModelSeed, default_seed
from turkish_code.yonlendirme.capability import CapabilitySet

DEFAULT_TIMEOUT_SECONDS = 30.0
HEALTH_CHECK_TIMEOUT_SECONDS = 5.0


class BaseOpenAICompatProvider:
    """A real OpenAI-compatible chat/embeddings adapter (doc 22 §7)."""

    def __init__(
        self,
        provider_id: str,
        *,
        base_url: str,
        api_key: str | None,
        tier_info: TierInfo,
        model_seeds: Mapping[str, ModelSeed],
        kind: ProviderKind = ProviderKind.CLOUD,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._id = provider_id
        self._kind = kind
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._tier_info = tier_info
        self._model_seeds = model_seeds
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> ProviderKind:
        return self._kind

    @property
    def is_offline_fallback(self) -> bool:
        """OpenAI-compatible providers (Groq/OpenRouter/NIM) are always
        primaries, never the offline fallback (doc 21 §4)."""
        return False

    @property
    def tier_info(self) -> TierInfo:
        return self._tier_info

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _seed(self, model_id: str) -> ModelSeed:
        return self._model_seeds.get(model_id, default_seed())

    async def list_models(self) -> Sequence[ModelInfo]:
        response = await self._client.get(
            f"{self._base_url}/models", headers=self._headers()
        )
        _raise_for_status(response)
        entries = response.json().get("data", [])
        return [self._to_model_info(entry["id"]) for entry in entries]

    def _to_model_info(self, model_id: str) -> ModelInfo:
        seed = self._seed(model_id)
        return ModelInfo(
            id=model_id,
            provider_id=self._id,
            roles=seed.roles,
            capabilities=seed.capabilities,
            context_window=seed.context_window,
            pricing=seed.pricing,
            tier=self._tier_info.tier,
            latency_profile=None,
            quality=None,
        )

    async def chat(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, object]] | None = None,
        opts: Mapping[str, object] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        body: dict[str, object] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = list(tools)
        if opts:
            body.update(opts)

        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json=body,
            headers=self._headers(),
        ) as response:
            _raise_for_status(response)
            async for line in response.aiter_lines():
                chunk = _parse_sse_line(line)
                if chunk is not None:
                    yield chunk

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        response = await self._client.post(
            f"{self._base_url}/embeddings",
            json={"model": model, "input": list(texts)},
            headers=self._headers(),
        )
        _raise_for_status(response)
        return [entry["embedding"] for entry in response.json()["data"]]

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        raise AppError(
            kind=ErrorKind.VALIDATION,
            code=CAPABILITY_UNSUPPORTED_CODE,
            message_key="hata.provider.capability_unsupported",
            retryable=False,
            context={"provider": self._id, "capability": "rerank"},
        )

    async def health(self) -> HealthStatus:
        try:
            response = await self._client.get(
                f"{self._base_url}/models",
                headers=self._headers(),
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException:
            return HealthStatus.DEGRADED
        except httpx.HTTPError:
            return HealthStatus.DOWN
        if response.status_code == 200:
            return HealthStatus.UP
        if response.status_code == 429:
            return HealthStatus.COOLING_DOWN
        if response.status_code >= 500:
            return HealthStatus.DOWN
        return HealthStatus.DEGRADED

    def capabilities(self, model: str) -> CapabilitySet:
        return self._seed(model).capabilities


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise AppError(
            kind=ErrorKind.PROVIDER,
            code=RATE_LIMIT_CODE,
            message_key="hata.provider.rate_limited",
            retryable=True,
        )
    if response.status_code >= 400:
        raise AppError(
            kind=ErrorKind.PROVIDER,
            code="provider.http_error",
            message_key="hata.provider.http_error",
            retryable=response.status_code >= 500,
            context={"status": response.status_code},
        )


def _parse_sse_line(line: str) -> ChatChunk | None:
    """Parse one OpenAI-compatible SSE ``data: {...}`` line, if present."""
    if not line.startswith("data: "):
        return None
    payload = line.removeprefix("data: ").strip()
    if payload == "[DONE]":
        return None
    event = json.loads(payload)
    choices = event.get("choices") or [{}]
    delta = choices[0].get("delta", {})
    usage_raw = event.get("usage")
    usage = (
        Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
        )
        if usage_raw
        else None
    )
    return ChatChunk(
        delta=delta.get("content") or "",
        finish_reason=choices[0].get("finish_reason"),
        usage=usage,
    )
