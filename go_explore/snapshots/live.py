from __future__ import annotations

from collections.abc import Callable
from time import monotonic

from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.metrics import SnapshotProcessingResult
from go_explore.snapshots.models import SnapshotContext


class AsyncLiveSnapshotSession:
    """Live hook surface for a running agent step stream."""

    def __init__(
        self,
        manager: AsyncSnapshotManager,
        *,
        clock: Callable[[], float] = monotonic,
    ):
        self._manager = manager
        self._clock = clock

    @property
    def manager(self) -> AsyncSnapshotManager:
        return self._manager

    async def process_step(self, context: SnapshotContext) -> SnapshotProcessingResult:
        return await self._manager.process_step_with_metrics(context, clock=self._clock)
