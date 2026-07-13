"""Ollama adapter (doc 22 §5.5) — the local/offline fallback (doc 21 §4, ADR-0008/0010).

Ollama's native HTTP API (loopback, no auth), distinct from the
OpenAI-compatible shape shared by Groq/OpenRouter/NIM — its own small,
real implementation rather than a forced fit into the shared base adapter.
Never the primary; the only provider expected to report
``is_offline_fallback=True`` (doc 21 §4).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence

import httpx

from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError, ErrorKind
from turkish_code.saglayicilar.provider import (
    CAPABILITY_UNSUPPORTED_CODE,
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

PROVIDER_ID = "ollama"
DEFAULT_TIMEOUT_SECONDS = 60.0
HEALTH_CHECK_TIMEOUT_SECONDS = 5.0

_UNLIMITED_TIER = TierInfo(tier="local", quota_limits={})
"""Ollama runs on the user's own machine — no provider-declared quota (doc 22 §5.5)."""


class OllamaProvider:
    """A real adapter over a local Ollama daemon (doc 22 §5.5)."""

    def __init__(
        self,
        *,
        base_url: str,
        model_seeds: Mapping[str, ModelSeed],
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_seeds = model_seeds
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def id(self) -> str:
        return PROVIDER_ID

    @property
    def kind(self) -> ProviderKind:
        return ProviderKind.LOCAL

    @property
    def is_offline_fallback(self) -> bool:
        return True

    @property
    def tier_info(self) -> TierInfo:
        return _UNLIMITED_TIER

    def _seed(self, model_id: str) -> ModelSeed:
        return self._model_seeds.get(model_id, default_seed())

    async def list_models(self) -> Sequence[ModelInfo]:
        response = await self._client.get(f"{self._base_url}/api/tags")
        _raise_for_status(response)
        entries = response.json().get("models", [])
        return [self._to_model_info(entry["name"]) for entry in entries]

    def _to_model_info(self, model_id: str) -> ModelInfo:
        seed = self._seed(model_id)
        return ModelInfo(
            id=model_id,
            provider_id=PROVIDER_ID,
            roles=seed.roles,
            capabilities=seed.capabilities,
            context_window=seed.context_window,
            pricing=None,
            tier="local",
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
        }
        if opts:
            body.update(opts)

        async with self._client.stream(
            "POST", f"{self._base_url}/api/chat", json=body
        ) as response:
            _raise_for_status(response)
            async for line in response.aiter_lines():
                chunk = _parse_ndjson_line(line)
                if chunk is not None:
                    yield chunk

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        vectors: list[Sequence[float]] = []
        for text in texts:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            _raise_for_status(response)
            vectors.append(response.json()["embedding"])
        return vectors

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        raise AppError(
            kind=ErrorKind.VALIDATION,
            code=CAPABILITY_UNSUPPORTED_CODE,
            message_key="hata.provider.capability_unsupported",
            retryable=False,
            context={"provider": PROVIDER_ID, "capability": "rerank"},
        )

    async def health(self) -> HealthStatus:
        try:
            response = await self._client.get(
                f"{self._base_url}/api/tags", timeout=HEALTH_CHECK_TIMEOUT_SECONDS
            )
        except httpx.TimeoutException:
            return HealthStatus.DEGRADED
        except httpx.HTTPError:
            return HealthStatus.DOWN
        return HealthStatus.UP if response.status_code == 200 else HealthStatus.DOWN

    def capabilities(self, model: str) -> CapabilitySet:
        return self._seed(model).capabilities


def create_ollama_provider(
    *,
    base_url: str,
    model_seeds: Mapping[str, ModelSeed],
    client: httpx.AsyncClient | None = None,
) -> OllamaProvider:
    """Build the Ollama ``Provider`` (doc 22 §5.5)."""
    return OllamaProvider(base_url=base_url, model_seeds=model_seeds, client=client)


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise AppError(
            kind=ErrorKind.PROVIDER,
            code="provider.http_error",
            message_key="hata.provider.http_error",
            retryable=response.status_code >= 500,
            context={"status": response.status_code},
        )


def _parse_ndjson_line(line: str) -> ChatChunk | None:
    """Parse one Ollama newline-delimited JSON chat line, if present."""
    if not line.strip():
        return None
    event = json.loads(line)
    content = event.get("message", {}).get("content", "")
    if not event.get("done"):
        return ChatChunk(delta=content)
    usage = Usage(
        prompt_tokens=event.get("prompt_eval_count", 0),
        completion_tokens=event.get("eval_count", 0),
    )
    return ChatChunk(delta=content, finish_reason="stop", usage=usage)
