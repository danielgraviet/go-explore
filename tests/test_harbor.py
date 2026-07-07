from __future__ import annotations

from pathlib import Path

from go_explore.harbor import HarborRunConfig, build_harbor_command


def test_build_harbor_command_omits_agent_when_using_import_path():
    config = HarborRunConfig(
        agent=None,
        model="anthropic/claude-haiku-4-5-20251001",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="snapshot-test",
        extra_args=(
            "--agent-import-path",
            "go_explore.agents.factory:snapshot_aware_terminus2_factory",
        ),
    )

    cmd = build_harbor_command(config)

    assert "--agent" not in cmd
    assert cmd == [
        "harbor",
        "run",
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
        "--task-name",
        "fix-git",
        "--job-name",
        "snapshot-test",
        "--export-traces",
        "--agent-import-path",
        "go_explore.agents.factory:snapshot_aware_terminus2_factory",
    ]
