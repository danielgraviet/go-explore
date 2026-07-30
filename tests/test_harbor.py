from __future__ import annotations

from pathlib import Path

import pytest

from go_explore.harbor import (
    HarborRunConfig,
    build_harbor_command,
    environment_with_repo_path,
    with_agent_kwarg,
)


def test_harbor_config_rejects_agent_and_import_path_together():
    config = HarborRunConfig(
        agent="terminus-2",
        agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
        dataset="terminal-bench@2.0",
    )

    with pytest.raises(ValueError, match="Set only one of agent or agent_import_path"):
        build_harbor_command(config)


def test_build_harbor_command_accepts_agent_import_path():
    config = HarborRunConfig(
        agent=None,
        agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
        model="anthropic/claude-haiku-4-5-20251001",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="snapshot-test",
    )

    cmd = build_harbor_command(config)

    assert cmd == [
        "harbor",
        "run",
        "--agent-import-path",
        "go_explore.agents.factory:SnapshotAwareTerminus2",
        "--env",
        "daytona",
        "--jobs-dir",
        "jobs",
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
        "--dataset",
        "terminal-bench@2.0",
        "--model",
        "anthropic/claude-haiku-4-5-20251001",
        "--include-task-name",
        "fix-git",
        "--job-name",
        "snapshot-test",
        "--export-traces",
    ]


def test_with_agent_kwarg_appends_new_key():
    result = with_agent_kwarg(("--ek", "foo=bar"), "token_budget", "1000")

    assert result == ("--ek", "foo=bar", "--ak", "token_budget=1000")


def test_with_agent_kwarg_replaces_existing_key():
    result = with_agent_kwarg(
        ("--ak", "token_budget=500", "--ak", "context_mode=none"),
        "token_budget",
        "1000",
    )

    assert result == ("--ak", "context_mode=none", "--ak", "token_budget=1000")


def test_environment_with_repo_path_precedes_existing_pythonpath():
    environment = environment_with_repo_path({"PYTHONPATH": "/tmp/other"})

    assert environment["PYTHONPATH"].split(":")[0].endswith("/go-explore")
    assert environment["PYTHONPATH"].endswith("/tmp/other")
