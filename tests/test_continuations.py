from __future__ import annotations

import json
from pathlib import Path

from go_explore.continuations import (
    ContinuationAttempt,
    ContinuationReport,
    build_snapshot_continuation_config,
    harbor_config_from_job,
    plan_snapshot_continuations,
    snapshot_prefix_for_trial,
)
from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import JobSummary, TrialSummary


def test_snapshot_prefix_for_trial_matches_daytona_snapshot_names():
    assert snapshot_prefix_for_trial("fix-git__abc123") == "go-explore-fix-git__abc123-step-"


def test_build_snapshot_continuation_config_restores_daytona_snapshot():
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="anthropic/claude-haiku-4-5-20251001",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )

    continuation_config = build_snapshot_continuation_config(
        root_config=root_config,
        snapshot_name="go-explore-fix-git__abc-step-2",
        job_name="cont-0",
    )

    assert continuation_config.environment_kwargs == (
        "snapshot_template_name=go-explore-fix-git__abc-step-2",
    )
    assert build_harbor_command(continuation_config) == [
        "harbor",
        "run",
        "--agent",
        "terminus-2",
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
        "--n-tasks",
        "1",
        "--job-name",
        "cont-0",
        "--export-traces",
        "--ek",
        "snapshot_template_name=go-explore-fix-git__abc-step-2",
    ]


def test_harbor_config_from_job_reconstructs_dataset_agent_and_model(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    job_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(tmp_path / "jobs"),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": "terminus-2",
                        "import_path": None,
                        "model_name": "anthropic/claude-haiku-4-5-20251001",
                    }
                ],
                "datasets": [
                    {
                        "name": "terminal-bench",
                        "version": "2.0",
                        "task_names": ["fix-git"],
                    }
                ],
                "tasks": [],
            }
        )
    )

    config = harbor_config_from_job(job_dir)

    assert config.jobs_dir == tmp_path / "jobs"
    assert config.agent == "terminus-2"
    assert config.env == "daytona"
    assert config.dataset == "terminal-bench@2.0"
    assert config.task_name == "fix-git"
    assert config.model == "anthropic/claude-haiku-4-5-20251001"


def test_harbor_config_from_job_preserves_import_path_shape(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    job_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(tmp_path / "jobs"),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": None,
                        "import_path": "go_explore.agents.factory:factory",
                        "model_name": "model-a",
                    }
                ],
                "datasets": [
                    {
                        "name": "terminal-bench",
                        "version": "2.0",
                        "task_names": ["fix-git"],
                    }
                ],
                "tasks": [],
            }
        )
    )

    config = harbor_config_from_job(job_dir)

    assert config.agent == "go_explore.agents.factory:factory"
    assert config.extra_args == ()


def test_plan_snapshot_continuations_records_parent_lineage():
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="model-a",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )
    root_summary = JobSummary(
        job_dir=Path("jobs/root"),
        n_total_trials=1,
        n_errors=0,
        mean=0.0,
        trials=(
            TrialSummary(
                trial_name="fix-git__root",
                task_name="fix-git",
                source="terminal-bench",
                reward=0.0,
                exception_type=None,
                exception_message=None,
            ),
        ),
    )

    plans = plan_snapshot_continuations(
        root_config=root_config,
        root_summary=root_summary,
        snapshots=("go-explore-fix-git__root-step-0", "go-explore-fix-git__root-step-1"),
        continuation_job_prefix="cont",
        model="model-b",
        max_snapshots=1,
    )

    assert len(plans) == 1
    assert plans[0].parent_job_dir == Path("jobs/root")
    assert plans[0].parent_trial_name == "fix-git__root"
    assert plans[0].snapshot_name == "go-explore-fix-git__root-step-0"
    assert plans[0].job_name == "cont-snapshot-0"
    assert "--model" in plans[0].command
    assert "model-b" in plans[0].command
    assert "--ek" in plans[0].command
    assert "snapshot_template_name=go-explore-fix-git__root-step-0" in plans[0].command


def test_continuation_report_tracks_any_success():
    failed = ContinuationAttempt(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        snapshot_name="snapshot-0",
        continuation_job_dir="jobs/cont-0",
        continuation_trial_name="fix-git__cont0",
        reward=0.0,
        exception_type=None,
    )
    passed = ContinuationAttempt(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        snapshot_name="snapshot-1",
        continuation_job_dir="jobs/cont-1",
        continuation_trial_name="fix-git__cont1",
        reward=1.0,
        exception_type=None,
    )

    report = ContinuationReport(
        root_job_dir="jobs/root",
        root_trial_name="fix-git__root",
        root_reward=0.0,
        attempts=(failed, passed),
    )

    assert report.any_success
    assert report.to_json_dict()["attempts"][1]["succeeded"] is True
