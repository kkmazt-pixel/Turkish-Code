"""NVIDIA NIM adapter (doc 22 §5.4) — OpenAI-compatible; cloud API key **or**
self-hosted on the user's own GPU (loopback, no key, no egress).

One of four peers, not flagship (ADR-0007/ADR-0008, doc 22 §5.4 "treated
exactly like the other primaries") — this adapter carries no special-casing
beyond which base URL/key mode the caller configured.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from turkish_code.saglayicilar.base_openai_compat import BaseOpenAICompatProvider
from turkish_code.saglayicilar.provider import ProviderKind, TierInfo
from turkish_code.saglayicilar.seeds import ModelSeed

PROVIDER_ID = "nvidia-nim"


def create_nvidia_nim_provider(
    *,
    base_url: str,
    api_key: str | None,
    tier_info: TierInfo,
    model_seeds: Mapping[str, ModelSeed],
    kind: ProviderKind = ProviderKind.CLOUD,
    client: httpx.AsyncClient | None = None,
) -> BaseOpenAICompatProvider:
    """Build the NVIDIA NIM :class:`~turkish_code.saglayicilar.provider.Provider`.

    ``kind=ProviderKind.LOCAL`` with ``api_key=None`` for a self-hosted NIM
    bound to loopback (doc 22 §5.4); ``ProviderKind.CLOUD`` with an API key
    for the NVIDIA-hosted path. Note: a self-hosted NIM is *not* the same as
    the Ollama offline fallback (doc 21 §4) — it's one of the four primaries,
    just running on the user's own GPU.
    """
    return BaseOpenAICompatProvider(
        PROVIDER_ID,
        base_url=base_url,
        api_key=api_key,
        tier_info=tier_info,
        model_seeds=model_seeds,
        kind=kind,
        client=client,
    )
