import asyncio

from go_explore.snapshots import AsyncLiveSnapshotSession, AsyncSnapshotManager, EveryAgentStepPolicy
from go_explore.snapshots.models import context_from_atif_step


def test_live_snapshot_session_records_monotonic_timing():
    class FakeClock:
        def __init__(self):
            self._values = iter(range(8))

        def __call__(self) -> float:
            return float(next(self._values))

    async def run_test():
        session = AsyncLiveSnapshotSession(
            AsyncSnapshotManager(policy=EveryAgentStepPolicy()),
            clock=FakeClock(),
        )
        context = context_from_atif_step(
            {
                "step_id": 7,
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

        result = await session.process_step(context)

        assert [record.id for record in result.records] == ["fix-git__abc123:step-7"]
        assert result.timing.started_at == 0.0
        assert result.timing.finished_at == 7.0
        assert result.timing.policy_seconds == 1.0
        assert result.timing.backend_seconds == 1.0
        assert result.timing.store_seconds == 1.0
        assert result.timing.total_seconds == 7.0
        assert result.timing.n_candidates == 1
        assert result.timing.n_snapshots == 1

    asyncio.run(run_test())
