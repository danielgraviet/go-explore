from __future__ import annotations

import json
from pathlib import Path

from go_explore.continuations import (
    ContinuationAttempt,
    ContinuationPlan,
    ContinuationReport,
    SnapshotSelectionMetadata,
    build_clean_start_config,
    build_snapshot_continuation_config,
    harbor_config_from_job,
    log_continuation_started,
    plan_start_state_baselines,
    plan_snapshot_continuations,
    snapshot_prefix_for_trial,
    write_plan_manifest,
)
from go_explore.events import EVENT_LOG_FILENAME
from go_explore.fixed_budget import (
    FixedBudgetPlanConfig,
    plan_fixed_budget_runs,
    write_fixed_budget_manifest,
)
from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import BudgetSummary, JobSummary, TrialSummary, summarize_job


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


def test_build_clean_start_config_uses_original_task_without_snapshot():
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="model-a",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )

    config = build_clean_start_config(
        root_config=root_config,
        job_name="cont-clean",
    )

    assert config.environment_kwargs == ()
    assert build_harbor_command(config) == [
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
        "model-a",
        "--include-task-name",
        "fix-git",
        "--n-tasks",
        "1",
        "--job-name",
        "cont-clean",
        "--export-traces",
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


def test_summarize_job_includes_complete_budget_metrics(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    trial_dir = job_dir / "trial-a"
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-a",
                "task_name": "fix-git",
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 3,
                    "n_cache_tokens": 2,
                    "cost_usd": 0.25,
                },
                "verifier_result": {"reward": 1.0},
                "started_at": "2026-07-06T16:01:38Z",
                "finished_at": "2026-07-06T16:01:48Z",
                "environment_setup": {
                    "started_at": "2026-07-06T16:01:38Z",
                    "finished_at": "2026-07-06T16:01:40Z",
                },
                "agent_execution": {
                    "started_at": "2026-07-06T16:01:40Z",
                    "finished_at": "2026-07-06T16:01:47Z",
                },
            }
        )
    )

    trial = summarize_job(job_dir).trials[0]

    assert trial.budget.n_input_tokens == 10
    assert trial.budget.n_output_tokens == 3
    assert trial.budget.n_cache_tokens == 2
    assert trial.budget.total_tokens == 15
    assert trial.budget.total_tokens_status == "complete"
    assert trial.budget.cost_usd == 0.25
    assert trial.budget.cost_usd_status == "complete"
    assert trial.budget.duration_seconds == 10.0
    assert trial.budget.duration_seconds_status == "complete"
    assert trial.budget.environment_setup_seconds == 2.0
    assert trial.budget.agent_execution_seconds == 7.0


def test_summarize_job_includes_snapshot_overhead_from_events(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    trial_dir = job_dir / "trial-a"
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-a",
                "task_name": "fix-git",
                "verifier_result": {"reward": 1.0},
            }
        )
    )
    (job_dir / EVENT_LOG_FILENAME).write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "snapshot_created",
                        "trial_name": "trial-a",
                        "snapshot_name": "snap-a",
                        "overhead_seconds": 1.25,
                    }
                ),
                json.dumps(
                    {
                        "event_type": "snapshot_created",
                        "run_id": "trial-a",
                        "snapshot_name": "snap-b",
                        "snapshot_backend_seconds": 2.5,
                    }
                ),
            ]
        )
        + "\n"
    )

    budget = summarize_job(job_dir).trials[0].budget

    assert budget.snapshot_overhead_seconds == 3.75
    assert budget.snapshot_overhead_seconds_status == "complete"


def test_summarize_job_marks_legacy_snapshot_overhead_unknown(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    trial_dir = job_dir / "trial-a"
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-a",
                "task_name": "fix-git",
                "verifier_result": {"reward": 1.0},
            }
        )
    )
    (job_dir / EVENT_LOG_FILENAME).write_text(
        json.dumps(
            {
                "event_type": "snapshot_created",
                "trial_name": "trial-a",
                "snapshot_name": "snap-a",
                "overhead_seconds": None,
            }
        )
        + "\n"
    )

    budget = summarize_job(job_dir).trials[0].budget

    assert budget.snapshot_overhead_seconds is None
    assert budget.snapshot_overhead_seconds_status == "unknown"


def test_summarize_job_marks_partial_budget_metrics(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    trial_dir = job_dir / "trial-a"
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-a",
                "task_name": "fix-git",
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 3,
                },
                "verifier_result": {"reward": 0.0},
                "started_at": "2026-07-06T16:01:38Z",
                "finished_at": "2026-07-06T16:01:48Z",
            }
        )
    )

    budget = summarize_job(job_dir).trials[0].budget

    assert budget.total_tokens == 13
    assert budget.total_tokens_status == "partial"
    assert budget.cost_usd is None
    assert budget.cost_usd_status == "unknown"


def test_summarize_job_marks_missing_budget_metrics_unknown(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    trial_dir = job_dir / "trial-a"
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "trial-a",
                "task_name": "fix-git",
                "verifier_result": {"reward": 0.0},
            }
        )
    )

    budget = summarize_job(job_dir).trials[0].budget

    assert budget.n_input_tokens is None
    assert budget.n_output_tokens is None
    assert budget.total_tokens is None
    assert budget.total_tokens_status == "unknown"
    assert budget.cost_usd is None
    assert budget.cost_usd_status == "unknown"
    assert budget.duration_seconds is None
    assert budget.duration_seconds_status == "unknown"


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

    assert config.agent is None
    assert config.agent_import_path == "go_explore.agents.factory:factory"
    assert config.extra_args == ()


def test_harbor_config_from_job_converts_custom_agent_name_to_import_path(tmp_path):
    job_dir = tmp_path / "jobs" / "root"
    job_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(tmp_path / "jobs"),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": "go_explore.agents.factory:SnapshotAwareTerminus2",
                        "import_path": None,
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

    assert config.agent is None
    assert config.agent_import_path == "go_explore.agents.factory:SnapshotAwareTerminus2"


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


def test_plan_snapshot_continuations_logs_selected_snapshots(tmp_path):
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="model-a",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )
    root_summary = JobSummary(
        job_dir=tmp_path / "jobs" / "root",
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
    event_log_path = root_summary.job_dir / EVENT_LOG_FILENAME

    plan_snapshot_continuations(
        root_config=root_config,
        root_summary=root_summary,
        snapshots=("snapshot-0", "snapshot-1"),
        continuation_job_prefix="cont",
        max_snapshots=2,
        event_log_path=event_log_path,
        selector_mode="test_selector",
    )

    events = [json.loads(line) for line in event_log_path.read_text().splitlines()]
    assert [event["event_type"] for event in events] == [
        "snapshot_selected",
        "snapshot_selected",
    ]
    assert [event["snapshot_name"] for event in events] == ["snapshot-0", "snapshot-1"]
    assert events[0]["schema_version"] == "go-explore-event-v1"
    assert events[0]["event_id"] == "fix-git__root:snapshot_selected:0:snapshot-0"
    assert events[0]["run_id"] == "fix-git__root"
    assert events[0]["job_dir"] == str(root_summary.job_dir)
    assert events[0]["selector_mode"] == "test_selector"


def test_plan_snapshot_continuations_logs_selector_metadata(tmp_path):
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="model-a",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )
    root_summary = JobSummary(
        job_dir=tmp_path / "jobs" / "root",
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
    event_log_path = root_summary.job_dir / EVENT_LOG_FILENAME

    plan_snapshot_continuations(
        root_config=root_config,
        root_summary=root_summary,
        snapshots=("snapshot-0",),
        continuation_job_prefix="cont",
        event_log_path=event_log_path,
        selector_mode="fallback",
        selection_metadata=(
            SnapshotSelectionMetadata(
                snapshot_name="snapshot-0",
                selector_mode="random",
                cell_key="{main.py}",
                priority=1.25,
                score=2.25,
                times_selected=3,
                selector_reasons=("seed=42",),
            ),
        ),
    )

    event = json.loads(event_log_path.read_text())
    assert event["snapshot_name"] == "snapshot-0"
    assert event["selector_mode"] == "random"
    assert event["selector_reasons"] == ["seed=42"]
    assert event["cell_key"] == "{main.py}"
    assert event["priority"] == 1.25
    assert event["score"] == 2.25
    assert event["times_selected"] == 3


def test_plan_start_state_baselines_records_modes_and_artifacts(tmp_path):
    root_config = HarborRunConfig(
        agent="terminus-2",
        model="model-a",
        env="daytona",
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name="root",
    )
    root_summary = JobSummary(
        job_dir=tmp_path / "jobs" / "root",
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

    plans = plan_start_state_baselines(
        root_config=root_config,
        root_summary=root_summary,
        continuation_job_prefix="claim1",
        start_state_types=("clean", "diff_only", "full_snapshot"),
        snapshots=("snapshot-a", "snapshot-b"),
        diff_path=tmp_path / "parent.diff",
        max_snapshots=1,
    )

    assert [plan.start_state_type for plan in plans] == [
        "clean",
        "diff_only",
        "full_snapshot",
    ]
    assert [plan.context_mode for plan in plans] == [
        "original_task_only",
        "original_task_only",
        "parent_summary",
    ]
    assert plans[0].snapshot_name is None
    assert plans[0].parent_artifacts == ()
    assert "--ek" not in plans[0].command
    assert plans[1].snapshot_name is None
    assert plans[1].parent_artifacts == (str(tmp_path / "parent.diff"),)
    assert plans[1].executor_status == "manifest_only"
    assert "--ek" not in plans[1].command
    assert plans[2].snapshot_name == "snapshot-a"
    assert plans[2].executor_status == "ready"
    assert "snapshot_template_name=snapshot-a" in plans[2].command


def test_write_plan_manifest_serializes_start_state_metadata(tmp_path):
    plan = ContinuationPlan(
        parent_job_dir=tmp_path / "jobs" / "root",
        parent_trial_name="fix-git__root",
        snapshot_name=None,
        job_name="claim1-diff-only",
        command=("harbor", "run"),
        start_state_type="diff_only",
        context_mode="original_task_only",
        parent_artifacts=(str(tmp_path / "parent.diff"),),
        executor_status="manifest_only",
    )
    manifest_path = tmp_path / "plans" / "start-state-plan.json"

    write_plan_manifest((plan,), manifest_path)

    data = json.loads(manifest_path.read_text())
    assert data["schema_version"] == "go-explore-start-state-plan-v1"
    assert data["plans"][0]["parent_snapshot"] is None
    assert data["plans"][0]["start_state_type"] == "diff_only"
    assert data["plans"][0]["context_mode"] == "original_task_only"
    assert data["plans"][0]["parent_artifacts"] == [str(tmp_path / "parent.diff")]
    assert data["plans"][0]["executor_status"] == "manifest_only"


def test_log_continuation_started_writes_lineage_event(tmp_path):
    event_log_path = tmp_path / "jobs" / "root" / EVENT_LOG_FILENAME
    plan = ContinuationPlan(
        parent_job_dir=tmp_path / "jobs" / "root",
        parent_trial_name="fix-git__root",
        snapshot_name="snapshot-0",
        job_name="cont-snapshot-0",
        command=("harbor", "run"),
    )

    log_continuation_started(
        plan,
        event_log_path=event_log_path,
        experiment_id="experiment-1",
    )

    events = [json.loads(line) for line in event_log_path.read_text().splitlines()]
    assert len(events) == 1
    event = events[0]
    assert event["schema_version"] == "go-explore-event-v1"
    assert event["event_type"] == "continuation_started"
    assert event["event_id"] == "cont-snapshot-0:continuation_started"
    assert event["experiment_id"] == "experiment-1"
    assert event["run_id"] == "fix-git__root"
    assert event["parent_run_id"] == "fix-git__root"
    assert event["parent_snapshot"] == "snapshot-0"
    assert event["child_run_id"] == "cont-snapshot-0"
    assert event["child_job_dir"] == str(tmp_path / "jobs" / "cont-snapshot-0")
    assert event["start_state_type"] == "full_snapshot"
    assert event["context_mode"] == "parent_summary"
    assert event["parent_artifacts"] == []
    assert event["executor_status"] == "ready"


def test_log_continuation_started_uses_plan_start_state_metadata(tmp_path):
    event_log_path = tmp_path / "jobs" / "root" / EVENT_LOG_FILENAME
    plan = ContinuationPlan(
        parent_job_dir=tmp_path / "jobs" / "root",
        parent_trial_name="fix-git__root",
        snapshot_name=None,
        job_name="cont-diff-only",
        command=("harbor", "run"),
        start_state_type="diff_only",
        context_mode="original_task_only",
        parent_artifacts=(str(tmp_path / "parent.diff"),),
        executor_status="manifest_only",
    )

    log_continuation_started(plan, event_log_path=event_log_path)

    event = json.loads(event_log_path.read_text())
    assert event["parent_snapshot"] is None
    assert event["start_state_type"] == "diff_only"
    assert event["context_mode"] == "original_task_only"
    assert event["parent_artifacts"] == [str(tmp_path / "parent.diff")]
    assert event["executor_status"] == "manifest_only"


def test_continuation_report_includes_start_state_fields():
    attempt = ContinuationAttempt(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        snapshot_name=None,
        continuation_job_dir="jobs/claim1-diff-only",
        continuation_trial_name=None,
        reward=None,
        exception_type="manifest-only",
        start_state_type="diff_only",
        context_mode="original_task_only",
        parent_artifacts=("jobs/root/parent.diff",),
    )
    report = ContinuationReport(
        root_job_dir="jobs/root",
        root_trial_name="fix-git__root",
        root_reward=0.0,
        attempts=(attempt,),
    )

    data = report.to_json_dict()
    assert data["attempts"][0]["snapshot_name"] is None
    assert data["attempts"][0]["start_state_type"] == "diff_only"
    assert data["attempts"][0]["context_mode"] == "original_task_only"
    assert data["attempts"][0]["parent_artifacts"] == ("jobs/root/parent.diff",)


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


def test_continuation_report_includes_budget_fields():
    attempt = ContinuationAttempt(
        parent_job_dir="jobs/root",
        parent_trial_name="fix-git__root",
        snapshot_name="snapshot-0",
        continuation_job_dir="jobs/cont-0",
        continuation_trial_name="fix-git__cont0",
        reward=1.0,
        exception_type=None,
        budget=BudgetSummary(
            n_input_tokens=5,
            n_output_tokens=7,
            total_tokens=12,
            cost_usd=0.12,
            duration_seconds=3.0,
            total_tokens_status="partial",
            cost_usd_status="complete",
            duration_seconds_status="complete",
        ),
    )
    report = ContinuationReport(
        root_job_dir="jobs/root",
        root_trial_name="fix-git__root",
        root_reward=0.0,
        attempts=(attempt,),
        root_budget=BudgetSummary(
            total_tokens=None,
            cost_usd=None,
            total_tokens_status="unknown",
            cost_usd_status="unknown",
        ),
    )

    data = report.to_json_dict()

    assert data["root_budget"]["total_tokens"] is None
    assert data["root_budget"]["total_tokens_status"] == "unknown"
    assert data["attempts"][0]["succeeded"] is True
    assert data["attempts"][0]["budget"]["n_input_tokens"] == 5
    assert data["attempts"][0]["budget"]["n_output_tokens"] == 7
    assert data["attempts"][0]["budget"]["total_tokens"] == 12
    assert data["attempts"][0]["budget"]["cost_usd"] == 0.12
    assert data["attempts"][0]["budget"]["duration_seconds"] == 3.0


def test_fixed_budget_planner_allocates_single_retry_and_branch_budgets():
    base_config = HarborRunConfig(
        agent="terminus-2",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        model="model-a",
        task_name="fix-git",
    )

    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id="pilot-1",
            base_config=base_config,
            job_prefix="pilot",
            total_token_budget=100_000,
            methods=("single", "retry", "random_branch", "promising_branch"),
            seeds=(3,),
            n_retries=5,
            n_branch_continuations=2,
            branch_root_fraction=0.3,
            snapshots=("snapshot-a", "snapshot-b"),
        )
    )

    jobs = manifest.jobs
    single = [job for job in jobs if job.method == "single"]
    retries = [job for job in jobs if job.method == "retry"]
    random_branch = [job for job in jobs if job.method == "random_branch"]
    promising_branch = [job for job in jobs if job.method == "promising_branch"]

    assert single[0].budget.token_budget == 100_000
    assert [job.budget.token_budget for job in retries] == [20_000] * 5
    assert [job.budget.token_budget for job in random_branch] == [
        30_000,
        35_000,
        35_000,
    ]
    assert [job.budget.token_budget for job in promising_branch] == [
        30_000,
        35_000,
        35_000,
    ]
    assert {job.seed for job in jobs} == {3}
    assert manifest.to_json_dict()["budget"]["enforcement"] == "planning_only"


def test_fixed_budget_planner_generates_method_commands_and_snapshot_children():
    base_config = HarborRunConfig(
        agent=None,
        agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        model="model-a",
        task_name="fix-git",
    )

    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id="pilot-1",
            base_config=base_config,
            job_prefix="pilot",
            total_token_budget=90_000,
            methods=("random_branch",),
            seeds=(11,),
            n_branch_continuations=2,
            branch_root_fraction=0.5,
            snapshots=("snapshot-a", "snapshot-b"),
        )
    )

    root, child_0, child_1 = manifest.jobs
    assert root.role == "root"
    assert root.start_state_type == "clean"
    assert root.selector_mode == "random"
    assert root.job_name == "pilot-random-branch-seed-11-root"
    assert "--agent-import-path" in root.command
    assert "--ek" not in root.command
    assert child_0.role == "continuation"
    assert child_0.start_state_type == "full_snapshot"
    assert child_0.context_mode == "parent_summary"
    assert child_0.selector_mode == "random"
    assert child_0.executor_status == "ready"
    assert "snapshot_template_name=" in " ".join(child_0.command)
    assert child_1.parent_run_id == root.job_name


def test_fixed_budget_planner_marks_branch_children_pending_without_snapshots():
    base_config = HarborRunConfig(
        agent="terminus-2",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        model="model-a",
        task_name="fix-git",
    )

    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id="pilot-1",
            base_config=base_config,
            job_prefix="pilot",
            total_token_budget=60_000,
            methods=("promising_branch",),
            seeds=(0,),
            n_branch_continuations=2,
            snapshots=(),
        )
    )

    _, child_0, child_1 = manifest.jobs
    assert child_0.executor_status == "pending_root_archive"
    assert child_0.command == ()
    assert child_0.parent_snapshot is None
    assert child_1.executor_status == "pending_root_archive"


def test_write_fixed_budget_manifest_serializes_budget_and_commands(tmp_path):
    base_config = HarborRunConfig(
        agent="terminus-2",
        env="daytona",
        jobs_dir=Path("jobs"),
        dataset="terminal-bench@2.0",
        model="model-a",
        task_name="fix-git",
    )
    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id="pilot-1",
            base_config=base_config,
            job_prefix="pilot",
            total_token_budget=10_000,
            methods=("single",),
            seeds=(0,),
        )
    )
    path = tmp_path / "plans" / "fixed-budget.json"

    write_fixed_budget_manifest(manifest, path)

    data = json.loads(path.read_text())
    assert data["schema_version"] == "go-explore-fixed-budget-plan-v1"
    assert data["experiment_id"] == "pilot-1"
    assert data["task_id"] == "fix-git"
    assert data["jobs"][0]["method"] == "single"
    assert data["jobs"][0]["budget"]["token_budget"] == 10_000
    assert data["jobs"][0]["command"][0:2] == ["harbor", "run"]
