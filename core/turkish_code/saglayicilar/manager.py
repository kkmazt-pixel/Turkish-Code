"""The provider manager (doc 21 §6) — registry, cache-backed enumeration, health.

Registers providers (via constructor injection — no global registry, PR-9),
maintains the unified model registry backed by the 24h model cache (doc 49),
and tracks per-provider health. Model-first **selection** is delegated to the
router (doc 45) — this module only *supplies* candidates (doc 21 §7/§22 #4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from turkish_code.hata import AppError, ErrorKind
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.cache.refresh import ModelCache
from turkish_code.saglayicilar.provider import HealthStatus, ModelInfo, Provider
from turkish_code.yonlendirme.capability import Role


class ProviderManager:
    """Registry + cache + health tracking over a fixed set of providers.

    The provider set is injected once at construction (doc 09 §7) — there is
    no runtime ``register()``; adding a provider means constructing the
    manager with it included (ADR-0014, no core changes).
    """

    def __init__(
        self, providers: Sequence[Provider], *, cache: ModelCache, clock: Clock
    ) -> None:
        if len({p.id for p in providers}) != len(providers):
            raise ValueError("provider ids must be unique")
        self._providers: Mapping[str, Provider] = {p.id: p for p in providers}
        self._cache = cache
        self._clock = clock

    def provider_ids(self) -> Sequence[str]:
        """The ids of every registered provider (doc 10 §13 handshake)."""
        return list(self._providers)

    def provider(self, provider_id: str) -> Provider:
        """Look up a registered provider by id.

        Raises:
            AppError: ``NotFound`` if ``provider_id`` isn't registered.
        """
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise AppError(
                kind=ErrorKind.NOT_FOUND,
                code="provider.unknown",
                message_key="hata.provider.unknown",
                retryable=False,
                context={"providerId": provider_id},
            ) from exc

    async def refresh_stale(self) -> None:
        """Refresh the cache for every provider whose entry is stale (doc 49 §5)."""
        now = self._clock.now()
        for provider_id, provider in self._providers.items():
            if self._cache.is_stale(provider_id, now=now):
                await self._refresh_one(provider_id, provider, now)

    async def _refresh_one(
        self, provider_id: str, provider: Provider, now: datetime
    ) -> None:
        models = await provider.list_models()
        self._cache.put(provider_id, models, fetched_at=now)

    def all_models(self) -> Sequence[ModelInfo]:
        """The flat, provider-independent model catalog (doc 21 §6) from cache."""
        catalog: list[ModelInfo] = []
        for provider_id in self._providers:
            entry = self._cache.get(provider_id)
            if entry is not None:
                catalog.extend(entry.models)
        return catalog

    def models_for_role(self, role: Role) -> Sequence[ModelInfo]:
        """The cached models across all providers that offer ``role``."""
        return [model for model in self.all_models() if role in model.roles]

    async def health_snapshot(self) -> Mapping[str, HealthStatus]:
        """Live health for every registered provider (doc 21 §9, doc 45 §5)."""
        return {
            provider_id: await provider.health()
            for provider_id, provider in self._providers.items()
        }
