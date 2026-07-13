"""OpenRouter adapter (doc 22 §5.3) — OpenAI-compatible, a multi-model gateway.

Its large, changing model list is exactly why the 24h model cache exists
(doc 49) — this adapter just answers ``list_models()`` honestly each time
it's asked; caching/dedup-against-direct-providers is the registry's job
(doc 21 §6), not this adapter's (doc 22 §3 single-responsibility).
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from turkish_code.saglayicilar.base_openai_compat import BaseOpenAICompatProvider
from turkish_code.saglayicilar.provider import ProviderKind, TierInfo
from turkish_code.saglayicilar.seeds import ModelSeed

PROVIDER_ID = "openrouter"


def create_openrouter_provider(
    *,
    base_url: str,
    api_key: str | None,
    tier_info: TierInfo,
    model_seeds: Mapping[str, ModelSeed],
    client: httpx.AsyncClient | None = None,
) -> BaseOpenAICompatProvider:
    """Build the OpenRouter ``Provider`` (doc 22 §5.3)."""
    return BaseOpenAICompatProvider(
        PROVIDER_ID,
        base_url=base_url,
        api_key=api_key,
        tier_info=tier_info,
        model_seeds=model_seeds,
        kind=ProviderKind.CLOUD,
        client=client,
    )
