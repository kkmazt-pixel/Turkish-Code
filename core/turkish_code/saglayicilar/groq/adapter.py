"""Groq adapter (doc 22 §5.2) — OpenAI-compatible, very low latency.

Groq's differentiator is time-to-first-token, measured by the benchmark
subsystem (doc 50), not anything special-cased here — it shares
:class:`~turkish_code.saglayicilar.base_openai_compat.BaseOpenAICompatProvider`
like OpenRouter and NVIDIA NIM (doc 22 §7). ``base_url`` is supplied by
configuration (doc 33 §12), never hardcoded, so this stays a thin factory.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from turkish_code.saglayicilar.base_openai_compat import BaseOpenAICompatProvider
from turkish_code.saglayicilar.provider import ProviderKind, TierInfo
from turkish_code.saglayicilar.seeds import ModelSeed

PROVIDER_ID = "groq"


def create_groq_provider(
    *,
    base_url: str,
    api_key: str | None,
    tier_info: TierInfo,
    model_seeds: Mapping[str, ModelSeed],
    client: httpx.AsyncClient | None = None,
) -> BaseOpenAICompatProvider:
    """Build the Groq ``Provider`` (doc 22 §5.2)."""
    return BaseOpenAICompatProvider(
        PROVIDER_ID,
        base_url=base_url,
        api_key=api_key,
        tier_info=tier_info,
        model_seeds=model_seeds,
        kind=ProviderKind.CLOUD,
        client=client,
    )
