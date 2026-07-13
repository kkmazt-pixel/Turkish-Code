"""Gemini adapter (doc 22 §5.1) — Google GenAI's own REST shape.

Distinct from the OpenAI-compatible providers (Groq/OpenRouter/NIM): Gemini
uses ``contents``/``parts``, a ``model`` role instead of ``assistant``, and a
separate ``systemInstruction`` field — its own real implementation rather
than forced into the shared base adapter (doc 22 §3 single-responsibility).
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

PROVIDER_ID = "gemini"
DEFAULT_TIMEOUT_SECONDS = 30.0
HEALTH_CHECK_TIMEOUT_SECONDS = 5.0


class GeminiProvider:
    """A real adapter over the Google GenAI REST API (doc 22 §5.1)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        tier_info: TierInfo,
        model_seeds: Mapping[str, ModelSeed],
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._tier_info = tier_info
        self._model_seeds = model_seeds
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def id(self) -> str:
        return PROVIDER_ID

    @property
    def kind(self) -> ProviderKind:
        return ProviderKind.CLOUD

    @property
    def is_offline_fallback(self) -> bool:
        return False

    @property
    def tier_info(self) -> TierInfo:
        return self._tier_info

    def _seed(self, model_id: str) -> ModelSeed:
        return self._model_seeds.get(model_id, default_seed())

    def _key_param(self) -> dict[str, str]:
        return {"key": self._api_key}

    async def list_models(self) -> Sequence[ModelInfo]:
        response = await self._client.get(
            f"{self._base_url}/v1beta/models", params=self._key_param()
        )
        _raise_for_status(response)
        entries = response.json().get("models", [])
        return [
            self._to_model_info(entry["name"].removeprefix("models/"))
            for entry in entries
        ]

    def _to_model_info(self, model_id: str) -> ModelInfo:
        seed = self._seed(model_id)
        return ModelInfo(
            id=model_id,
            provider_id=PROVIDER_ID,
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
        body = _to_gemini_request(messages)
        params = {**self._key_param(), "alt": "sse"}

        async with self._client.stream(
            "POST",
            f"{self._base_url}/v1beta/models/{model}:streamGenerateContent",
            params=params,
            json=body,
        ) as response:
            _raise_for_status(response)
            async for line in response.aiter_lines():
                chunk = _parse_sse_line(line)
                if chunk is not None:
                    yield chunk

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        vectors: list[Sequence[float]] = []
        for text in texts:
            response = await self._client.post(
                f"{self._base_url}/v1beta/models/{model}:embedContent",
                params=self._key_param(),
                json={"content": {"parts": [{"text": text}]}},
            )
            _raise_for_status(response)
            vectors.append(response.json()["embedding"]["values"])
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
                f"{self._base_url}/v1beta/models",
                params=self._key_param(),
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


def create_gemini_provider(
    *,
    base_url: str,
    api_key: str,
    tier_info: TierInfo,
    model_seeds: Mapping[str, ModelSeed],
    client: httpx.AsyncClient | None = None,
) -> GeminiProvider:
    """Build the Gemini ``Provider`` (doc 22 §5.1)."""
    return GeminiProvider(
        base_url=base_url,
        api_key=api_key,
        tier_info=tier_info,
        model_seeds=model_seeds,
        client=client,
    )


def _to_gemini_request(messages: Sequence[ChatMessage]) -> dict[str, object]:
    """Map our chat messages to Gemini's ``contents``/``systemInstruction`` shape."""
    contents = []
    system_parts = []
    for message in messages:
        if message.role == "system":
            system_parts.append({"text": message.content})
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message.content}]})
    body: dict[str, object] = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": system_parts}
    return body


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
    """Parse one Gemini ``streamGenerateContent`` SSE ``data: {...}`` line."""
    if not line.startswith("data: "):
        return None
    payload = line.removeprefix("data: ").strip()
    if not payload:
        return None
    event = json.loads(payload)
    candidates = event.get("candidates") or [{}]
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    finish_reason = candidate.get("finishReason")

    usage_raw = event.get("usageMetadata")
    usage = (
        Usage(
            prompt_tokens=usage_raw.get("promptTokenCount", 0),
            completion_tokens=usage_raw.get("candidatesTokenCount", 0),
        )
        if usage_raw
        else None
    )
    return ChatChunk(
        delta=text,
        finish_reason="stop" if finish_reason else None,
        usage=usage,
    )
