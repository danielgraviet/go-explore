import asyncio
from pathlib import Path

from go_explore.snapshots import AsyncSnapshotManager, EveryAgentStepPolicy, SnapshotHandle
from go_explore.snapshots.replay import process_atif_trajectory


def test_process_atif_trajectory_calls_snapshotting_once_per_agent_action():
    class CountingBackend:
        def __init__(self):
            self.calls: list[tuple[str, int]] = []

        async def create_snapshot(self, candidate, context):
            self.calls.append((candidate.id, context.step_id))
            return SnapshotHandle(
                backend="noop",
                environment_id=f"env-{context.step_id}",
                restore_ref=f"restore-{candidate.id}",
            )

    async def run_test():
        backend = CountingBackend()
        manager = AsyncSnapshotManager(
            policy=EveryAgentStepPolicy(),
            backend=backend,
        )
        trajectory_path = Path("tests/fixtures/atif_trajectory.json")

        records = await process_atif_trajectory(
            trajectory_path,
            manager,
            trial_name="fix-git__abc123",
        )

        assert backend.calls == [
            ("fix-git__abc123:step-2", 2),
            ("fix-git__abc123:step-3", 3),
        ]
        assert [record.id for record in records] == [
            "fix-git__abc123:step-2",
            "fix-git__abc123:step-3",
        ]
        assert [record.backend for record in records] == ["noop", "noop"]
        assert [record.candidate.metadata["snapshot_backend"] for record in records] == [
            "noop",
            "noop",
        ]
        assert [record.candidate.trace_path for record in records] == [
            trajectory_path,
            trajectory_path,
        ]
        assert manager.list() == records

    asyncio.run(run_test())
