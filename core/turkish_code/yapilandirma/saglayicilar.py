"""Provider configuration value types (doc 33 §12, doc 34 §1).

Keys/endpoints are resolved from the environment only — never from
``settings.toml`` — so a secret can never end up in a config file a user
might share or commit (doc 34 §1 "light key handling").

``default_cost_mode`` is kept as a validated raw string here, not the
``yonlendirme.mod.CostMode`` enum: ``yapilandirma`` is a foundational leaf
(doc 09 §7) and must not depend on the routing layer. The composition root,
which already wires both, converts it at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    """One cloud provider's endpoint + key, both optional (doc 33 §12).

    ``None`` for either means the provider isn't configured; the composition
    root skips constructing an adapter for it (doc 21 §12 "enabled where a
    key is present").
    """

    base_url: str | None
    api_key: str | None

    @property
    def is_configured(self) -> bool:
        return self.base_url is not None and self.api_key is not None


@dataclass(frozen=True, slots=True)
class ProvidersConfig:
    """The resolved provider layer configuration (doc 33 §12, doc 21 §12)."""

    gemini: ProviderCredentials
    groq: ProviderCredentials
    openrouter: ProviderCredentials
    nvidia_nim: ProviderCredentials
    ollama_base_url: str
    """Ollama needs no key (local, doc 22 §5.5); always has a default (doc 22)."""

    default_cost_mode: str
    """One of ``"performance"``/``"balanced"``/``"economy"`` (doc 17 §4b)."""
