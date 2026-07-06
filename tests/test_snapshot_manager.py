import asyncio

from go_explore.snapshots import (
    AsyncSnapshotManager,
    DaytonaSnapshotBackend,
    EveryAgentStepPolicy,
    InterestingAgentStepPolicy,
    SnapshotCandidate,
    SnapshotEvent,
    SnapshotRecord,
    context_from_atif_step,
)


def test_snapshot_manager_processes_policy_candidates_into_records():
    async def run_test():
        manager = AsyncSnapshotManager(policy=EveryAgentStepPolicy())
        context = context_from_atif_step(
            {
                "step_id": 2,
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "bash_command",
                        "arguments": {"keystrokes": "git status\n"},
                    }
                ],
            },
            trial_name="fix-git__abc123",
        )

        records = await manager.process_step(context)

        assert len(records) == 1
        assert records[0].id == "fix-git__abc123:step-2"
        assert records[0].backend == "noop"
        assert records[0].candidate.command == "git status"
        assert records[0].candidate.metadata["snapshot_backend"] == "noop"
        assert records[0].description == "agent_step | trial=fix-git__abc123 | step=2 | agent step"
        assert manager.get("fix-git__abc123:step-2") == records[0]
        assert manager.list() == records

    asyncio.run(run_test())


def test_snapshot_manager_does_not_store_when_policy_returns_no_candidates():
    async def run_test():
        manager = AsyncSnapshotManager(policy=InterestingAgentStepPolicy())
        context = context_from_atif_step(
            {
                "step_id": 2,
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "bash_command",
                        "arguments": {"keystrokes": "ls\n"},
                    }
                ],
                "observation": {"results": [{"content": "README.md"}]},
            },
            trial_name="trial",
        )

        assert await manager.process_step(context) == []
        assert manager.list() == []

    asyncio.run(run_test())


def test_snapshot_manager_accepts_replaceable_store():
    class RecordingStore:
        def __init__(self):
            self.records: dict[str, SnapshotRecord] = {}
            self.put_calls: list[str] = []

        def put(self, record: SnapshotRecord) -> None:
            self.put_calls.append(record.id)
            self.records[record.id] = record

        def get(self, snapshot_id: str) -> SnapshotRecord | None:
            return self.records.get(snapshot_id)

        def list(self) -> list[SnapshotRecord]:
            return list(self.records.values())

    store = RecordingStore()
    async def run_test():
        manager = AsyncSnapshotManager(policy=EveryAgentStepPolicy(), store=store)
        context = context_from_atif_step(
            {"step_id": 3, "source": "agent"},
            trial_name="trial",
        )

        records = await manager.process_step(context)

        assert store.put_calls == ["trial:step-3"]
        assert store.get("trial:step-3") == records[0]

    asyncio.run(run_test())


def test_snapshot_manager_accepts_replaceable_backend():
    class RecordingBackend:
        def __init__(self):
            self.calls: list[str] = []

        async def create_snapshot(
            self,
            candidate: SnapshotCandidate,
            context,
        ):
            from go_explore.snapshots import SnapshotHandle
            self.calls.append(candidate.id)
            return SnapshotHandle(
                backend="recording",
                environment_id=f"env-{context.step_id}",
                restore_ref=f"restore-{candidate.id}",
                metadata={"backend_note": "captured"},
            )

    backend = RecordingBackend()
    async def run_test():
        manager = AsyncSnapshotManager(policy=EveryAgentStepPolicy(), backend=backend)
        context = context_from_atif_step(
            {"step_id": 4, "source": "agent"},
            trial_name="trial",
        )

        records = await manager.process_step(context)

        assert backend.calls == ["trial:step-4"]
        assert records[0].backend == "recording"
        assert records[0].candidate.environment_id == "env-4"
        assert records[0].candidate.restore_ref == "restore-trial:step-4"
        assert records[0].candidate.metadata["snapshot_backend"] == "recording"
        assert records[0].candidate.metadata["backend_note"] == "captured"

    asyncio.run(run_test())


def test_async_snapshot_manager_uses_daytona_backend_before_storing():
    class FakeDaytonaSandbox:
        id = "sandbox-123"

        def __init__(self):
            self.created_snapshots: list[tuple[str, float | None]] = []

        async def _experimental_create_snapshot(
            self,
            name: str,
            timeout: float | None = 60,
        ) -> None:
            self.created_snapshots.append((name, timeout))

    async def run_test():
        sandbox = FakeDaytonaSandbox()
        backend = DaytonaSnapshotBackend(
            sandbox,
            timeout=12,
            name_prefix="test-prefix",
        )
        manager = AsyncSnapshotManager(
            policy=EveryAgentStepPolicy(),
            backend=backend,
        )
        context = context_from_atif_step(
            {
                "step_id": 5,
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "bash_command",
                        "arguments": {"keystrokes": "git status\n"},
                    }
                ],
            },
            trial_name="fix-git__abc123",
        )

        records = await manager.process_step(context)

        assert sandbox.created_snapshots == [("test-prefix-fix-git__abc123-step-5", 12)]
        assert len(records) == 1
        assert records[0].backend == "daytona"
        assert records[0].candidate.environment_id == "sandbox-123"
        assert records[0].candidate.restore_ref == "test-prefix-fix-git__abc123-step-5"
        assert records[0].candidate.metadata["snapshot_backend"] == "daytona"
        assert (
            records[0].candidate.metadata["daytona_snapshot_name"]
            == "test-prefix-fix-git__abc123-step-5"
        )
        assert manager.get("fix-git__abc123:step-5") == records[0]

    asyncio.run(run_test())
