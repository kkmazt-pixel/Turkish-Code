"""Shared provenance identifiers (doc 26 §Timeline, doc 11 §5, doc 12 §4).

``RunId``/``EventId`` are opaque references into the Event Journal / Timeline
(doc 26), which doesn't exist yet. They are real, typed identifiers — not
placeholders — but carry no query capability until Timeline is implemented;
that is an explicit, documented gap, not a hidden one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunId:
    """Identifies one reasoning run (doc 15/doc 26)."""

    value: str


@dataclass(frozen=True, slots=True)
class EventId:
    """Identifies one Timeline event within a run (doc 26)."""

    value: str


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    """A pointer to the Timeline event that produced something (doc 11 §5, doc 12 §4).

    Lets the user ask "why do you think this?" (P4) once Timeline (doc 26)
    can resolve it; today it is a real, structured reference with nothing yet
    to query it against.
    """

    run_id: RunId
    event_id: EventId
