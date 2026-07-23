import asyncio
import dataclasses

from go_explore.snapshots import (
    AsyncSnapshotManager,
    ArchiveStore,
    DaytonaSnapshotBackend,
    EveryAgentStepPolicy,
    InterestingAgentStepPolicy,
    SnapshotCandidate,
    SnapshotEvent,
    SnapshotRecord,
    context_from_atif_step,
)
from go_explore.snapshots.models import CONTEXT_FILE_PATH


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


def test_snapshot_manager_deletes_pruned_remote_snapshots(tmp_path):
    class TwoSnapshotsSameCellPolicy:
        def candidates_for_step(self, context):
            return [
                SnapshotCandidate(
                    id=f"{context.trial_name}:step-{context.step_id}-low",
                    event=SnapshotEvent.FILE_EDIT,
                    restore_ref="s-low",
                    changed_files=("main.py",),
                    metadata={
                        "trial_name": context.trial_name,
                        "step_id": str(context.step_id),
                    },
                ),
                SnapshotCandidate(
                    id=f"{context.trial_name}:step-{context.step_id}-high",
                    event=SnapshotEvent.TEST_RUN,
                    restore_ref="s-high",
                    changed_files=("main.py",),
                    tests_passed=1,
                    tests_failed=0,
                    metadata={
                        "trial_name": context.trial_name,
                        "step_id": str(context.step_id),
                    },
                ),
            ]

    class RecordingBackend:
        def __init__(self):
            self.deleted: list[str] = []

        async def create_snapshot(self, candidate, context):
            from go_explore.snapshots import SnapshotHandle

            return SnapshotHandle(
                backend="recording",
                restore_ref=candidate.restore_ref,
            )

        async def delete_snapshot(self, snapshot_name: str) -> None:
            self.deleted.append(snapshot_name)

    async def run_test():
        backend = RecordingBackend()
        manager = AsyncSnapshotManager(
            policy=TwoSnapshotsSameCellPolicy(),
            store=ArchiveStore(path=tmp_path / "archive.json"),
            backend=backend,
        )
        context = context_from_atif_step(
            {"step_id": 4, "source": "agent"},
            trial_name="trial",
        )

        await manager.process_step(context)

        assert backend.deleted == ["s-low"]

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


def test_daytona_backend_writes_trajectory_summary_before_snapshotting():
    """The running trajectory summary should land on disk before the snapshot is taken,
    so a child restored from that snapshot can read it back."""

    class FakeFileSystem:
        def __init__(self):
            self.uploads: list[tuple[bytes, str]] = []

        async def upload_file(self, src: bytes, dst: str) -> None:
            self.uploads.append((src, dst))

    class FakeDaytonaSandbox:
        id = "sandbox-123"

        def __init__(self):
            self.fs = FakeFileSystem()
            self.snapshot_taken_after_upload: bool | None = None

        async def _experimental_create_snapshot(
            self,
            name: str,
            timeout: float | None = 60,
        ) -> None:
            self.snapshot_taken_after_upload = len(self.fs.uploads) == 1

    async def run_test():
        sandbox = FakeDaytonaSandbox()
        backend = DaytonaSnapshotBackend(sandbox, timeout=12, name_prefix="test-prefix")
        manager = AsyncSnapshotManager(policy=EveryAgentStepPolicy(), backend=backend)
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
        context = dataclasses.replace(
            context, trajectory_summary="step 0: pip install -> ok\nstep 5: git status -> ok"
        )

        await manager.process_step(context)

        assert sandbox.fs.uploads == [
            (
                b"step 0: pip install -> ok\nstep 5: git status -> ok",
                CONTEXT_FILE_PATH,
            )
        ]
        assert sandbox.snapshot_taken_after_upload is True

    asyncio.run(run_test())
