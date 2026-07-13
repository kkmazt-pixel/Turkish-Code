"""Routing & orchestration subsystem (doc 45) — the model-first router.

Composes the capability taxonomy (doc 46), scoring (doc 47), quota/tier
management (doc 48), and benchmark evidence (doc 50) into the decision that
picks "which model, on which provider, right now" for a requested capability.

Note: this package's own ``__init__`` deliberately does **not** re-export
``candidates``/``router``/``resilience``/``decision`` — those modules import
:mod:`turkish_code.saglayicilar`, which itself imports the leaf
``turkish_code.yonlendirme.capability`` subpackage. Re-exporting them here
would force this package's ``__init__`` to execute before its own
``capability`` child finishes initializing, creating a circular import.
Import them directly, e.g. ``from turkish_code.yonlendirme.router import select``.
"""
