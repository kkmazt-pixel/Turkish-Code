"""Tests for the thin Groq/OpenRouter/NVIDIA-NIM factory wrappers (doc 22 §5.2-5.4).

These only verify wiring (provider id, kind); the shared request/response
logic is covered by ``test_base_openai_compat.py``.
"""

from __future__ import annotations

import httpx
from turkish_code.saglayicilar.groq.adapter import create_groq_provider
from turkish_code.saglayicilar.nvidia_nim.adapter import create_nvidia_nim_provider
from turkish_code.saglayicilar.openrouter.adapter import create_openrouter_provider
from turkish_code.saglayicilar.provider import ProviderKind, TierInfo

_TIER = TierInfo(tier="free", quota_limits={})
_CLIENT = httpx.AsyncClient(
    transport=httpx.MockTransport(lambda r: httpx.Response(200))
)


def test_groq_provider_id_and_kind() -> None:
    provider = create_groq_provider(
        base_url="https://example.test",
        api_key="k",
        tier_info=_TIER,
        model_seeds={},
        client=_CLIENT,
    )
    assert provider.id == "groq"
    assert provider.kind is ProviderKind.CLOUD
    assert provider.is_offline_fallback is False


def test_openrouter_provider_id_and_kind() -> None:
    provider = create_openrouter_provider(
        base_url="https://example.test",
        api_key="k",
        tier_info=_TIER,
        model_seeds={},
        client=_CLIENT,
    )
    assert provider.id == "openrouter"
    assert provider.kind is ProviderKind.CLOUD


def test_nvidia_nim_cloud_mode() -> None:
    provider = create_nvidia_nim_provider(
        base_url="https://example.test",
        api_key="k",
        tier_info=_TIER,
        model_seeds={},
        client=_CLIENT,
    )
    assert provider.id == "nvidia-nim"
    assert provider.kind is ProviderKind.CLOUD
    assert provider.is_offline_fallback is False


def test_nvidia_nim_self_hosted_mode_is_local_but_not_fallback() -> None:
    provider = create_nvidia_nim_provider(
        base_url="http://localhost:8000",
        api_key=None,
        tier_info=_TIER,
        model_seeds={},
        kind=ProviderKind.LOCAL,
        client=_CLIENT,
    )
    assert provider.kind is ProviderKind.LOCAL
    assert provider.is_offline_fallback is False
