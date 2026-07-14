"""Composition root — the one place that wires concrete implementations (doc 09 §7).

Everything else depends on interfaces; only this module knows the concrete
classes, constructing the object graph by explicit constructor injection. There
are no module-level singletons and no import-time side effects (PR-9): building a
container is an ordinary function call that returns a fresh graph.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

import httpx

from turkish_code import __version__
from turkish_code.depo.alan import StorageEngine
from turkish_code.depo.yerlesim import StorageLayout
from turkish_code.gozlem.collect import InMemoryMetricsCollector, MetricsCollector
from turkish_code.gunluk.kayitci import Logger, StructuredLogger
from turkish_code.gunluk.redaksiyon import FieldNameRedactor
from turkish_code.kanal.aktarim import Transport
from turkish_code.kanal.sunucu import AsyncCoreChannel
from turkish_code.kanal.uygulama import register_app_handlers
from turkish_code.ortak.saat import Clock, SystemClock
from turkish_code.saglayicilar.cache import InMemoryModelCache, ModelCache
from turkish_code.saglayicilar.gemini.adapter import create_gemini_provider
from turkish_code.saglayicilar.groq.adapter import create_groq_provider
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.nvidia_nim.adapter import create_nvidia_nim_provider
from turkish_code.saglayicilar.ollama.adapter import create_ollama_provider
from turkish_code.saglayicilar.openrouter.adapter import create_openrouter_provider
from turkish_code.saglayicilar.provider import Provider, TierInfo
from turkish_code.yapilandirma.ayarlar import Settings
from turkish_code.yapilandirma.saglayicilar import ProviderCredentials
from turkish_code.yonlendirme.benchmark.store import (
    BenchmarkStore,
    InMemoryBenchmarkStore,
)
from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore, QuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker

_UNLIMITED_TIER = TierInfo(tier="unknown", quota_limits={})
"""Placeholder tier until real per-provider limits are curated (doc 48 §10)."""


@dataclass(frozen=True, slots=True)
class Container:
    """The wired Çekirdek services (doc 09 §7).

    Holds fully-constructed dependencies to be passed explicitly to subsystems.
    Extended additively as subsystems come online (YAGNI: only what exists today).
    """

    settings: Settings
    clock: Clock
    logger: Logger
    provider_manager: ProviderManager
    quota_tracker: QuotaTracker
    benchmark_store: BenchmarkStore
    metrics: MetricsCollector
    default_cost_mode: CostMode


def build_container(
    settings: Settings,
    *,
    clock: Clock | None = None,
    log_stream: TextIO | None = None,
    http_client: httpx.AsyncClient | None = None,
    model_cache: ModelCache | None = None,
    quota_store: QuotaStore | None = None,
) -> Container:
    """Construct the object graph for ``settings`` (doc 09 §7).

    ``clock``/``log_stream``/``http_client``/``model_cache``/``quota_store``
    are all injectable to make the graph testable; production defaults are
    the real clock, stderr (doc 09 §16), a fresh ``httpx.AsyncClient``, and
    process-lifetime in-memory stores (Storage, doc 29, doesn't exist yet).
    """
    resolved_clock: Clock = clock if clock is not None else SystemClock()
    stream: TextIO = log_stream if log_stream is not None else sys.stderr
    logger = StructuredLogger(
        stream=stream,
        clock=resolved_clock,
        min_level=settings.log_level,
        redactor=FieldNameRedactor(),
    )

    client = http_client if http_client is not None else httpx.AsyncClient()
    providers = _build_providers(settings, client=client)
    provider_manager = ProviderManager(
        providers,
        cache=model_cache if model_cache is not None else InMemoryModelCache(),
        clock=resolved_clock,
    )
    quota_tracker = QuotaTracker(
        quota_store if quota_store is not None else InMemoryQuotaStore(), resolved_clock
    )

    return Container(
        settings=settings,
        clock=resolved_clock,
        logger=logger,
        provider_manager=provider_manager,
        quota_tracker=quota_tracker,
        benchmark_store=InMemoryBenchmarkStore(),
        metrics=InMemoryMetricsCollector(),
        default_cost_mode=CostMode(settings.providers.default_cost_mode),
    )


async def build_storage(settings: Settings) -> StorageEngine:
    """Bring durable storage online for ``settings`` (doc 29 §5).

    Opens the App DB and migrates it forward, returning the engine that mints
    per-workspace stores (``open_workspace``). Async — unlike the pure
    :func:`build_container` graph it performs I/O (writer threads, migrations),
    so it is a separate entry point the stateful subsystems draw from as they
    come online. The caller owns the engine's lifecycle (``aclose``).
    """
    layout = StorageLayout(settings.paths.data_dir)
    return await StorageEngine.open(layout, settings.storage)


def build_channel(
    container: Container,
    transport: Transport,
    *,
    session_token: str = "",
) -> AsyncCoreChannel:
    """Wire a Core Channel server over ``transport`` for ``container`` (doc 10).

    Registers the ``app.*`` handlers (doc 10 §13/§67); further subsystem
    handlers (``memory.*``, ``chat.*``, …) are registered the same way as
    their own subsystems come online — this is additive, not a God object.
    """
    channel = AsyncCoreChannel(transport)
    register_app_handlers(
        register=channel.register,
        core_version=__version__,
        session_token=session_token,
        provider_manager=container.provider_manager,
        on_shutdown=channel.request_shutdown,
    )
    return channel


def _build_providers(
    settings: Settings, *, client: httpx.AsyncClient
) -> list[Provider]:
    """Construct only the providers that are configured (doc 21 §12), plus Ollama.

    No curated capability seeds exist yet (doc 46 §6 is `OPEN`); every model
    gets the conservative default seed until real data is added — a documented
    gap, not a placeholder (adapters remain fully real and correct).
    """
    providers: list[Provider] = []
    creds = settings.providers

    if creds.gemini.is_configured:
        providers.append(_gemini(creds.gemini, client))
    if creds.groq.is_configured:
        providers.append(_groq(creds.groq, client))
    if creds.openrouter.is_configured:
        providers.append(_openrouter(creds.openrouter, client))
    if creds.nvidia_nim.is_configured:
        providers.append(_nvidia_nim(creds.nvidia_nim, client))

    providers.append(
        create_ollama_provider(
            base_url=creds.ollama_base_url, model_seeds={}, client=client
        )
    )
    return providers


def _gemini(creds: ProviderCredentials, client: httpx.AsyncClient) -> Provider:
    assert creds.base_url is not None and creds.api_key is not None
    return create_gemini_provider(
        base_url=creds.base_url,
        api_key=creds.api_key,
        tier_info=_UNLIMITED_TIER,
        model_seeds={},
        client=client,
    )


def _groq(creds: ProviderCredentials, client: httpx.AsyncClient) -> Provider:
    assert creds.base_url is not None
    return create_groq_provider(
        base_url=creds.base_url,
        api_key=creds.api_key,
        tier_info=_UNLIMITED_TIER,
        model_seeds={},
        client=client,
    )


def _openrouter(creds: ProviderCredentials, client: httpx.AsyncClient) -> Provider:
    assert creds.base_url is not None
    return create_openrouter_provider(
        base_url=creds.base_url,
        api_key=creds.api_key,
        tier_info=_UNLIMITED_TIER,
        model_seeds={},
        client=client,
    )


def _nvidia_nim(creds: ProviderCredentials, client: httpx.AsyncClient) -> Provider:
    assert creds.base_url is not None
    return create_nvidia_nim_provider(
        base_url=creds.base_url,
        api_key=creds.api_key,
        tier_info=_UNLIMITED_TIER,
        model_seeds={},
        client=client,
    )
