"""Tool execution context (doc 20 §5/§11) — the ambient "how" of one call.

Distinct from :class:`~turkish_code.araclar.modeller.ToolRequest` (the *inputs*),
:class:`ToolContext` carries the invocation's correlation ids, the cooperative
:class:`~turkish_code.araclar.iptal.CancellationToken` a tool checks so it can
stop promptly, and the :class:`~turkish_code.araclar.akis.ProgressSink` it reports
incremental work to (doc 20 §7/§14) — all without reaching for global state
(PR-9, doc 09 §6). The dispatcher (:mod:`turkish_code.araclar.dagitici`) builds
it per call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from turkish_code.araclar.akis import NullProgressSink, ProgressSink
from turkish_code.araclar.iptal import CancellationToken
from turkish_code.araclar.modeller import ToolProgress
from turkish_code.ortak.kimlik import RunId


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Ambient context handed to a tool at execution (doc 20 §5).

    Attributes:
        call_id: The invocation id, echoed from the request for correlation
            across cancellation/progress/result (doc 20 §11).
        run_id: The reasoning run this call belongs to (doc 26 provenance), or
            ``None`` when invoked outside a run.
        cancellation: The cooperative cancellation token for this call; tools
            check :attr:`CancellationToken.is_cancelled` at checkpoints (doc 20
            §14). ``None`` when the caller supplies no token.
        progress: The sink incremental :class:`ToolProgress` events are reported
            to (doc 20 §7); defaults to a drop-everything sink.
    """

    call_id: str
    run_id: RunId | None = None
    cancellation: CancellationToken | None = None
    progress: ProgressSink = field(default_factory=NullProgressSink)

    async def emit(
        self,
        message: str,
        *,
        fraction: float | None = None,
        payload: object = None,
    ) -> None:
        """Report an incremental progress event for this call (doc 20 §7).

        A convenience over :attr:`progress`: stamps the event with this call's
        id so tools need not repeat it.
        """
        await self.progress.emit(
            ToolProgress(
                call_id=self.call_id,
                message=message,
                fraction=fraction,
                payload=payload,
            )
        )
