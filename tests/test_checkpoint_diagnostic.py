import json

import pytest

from go_explore.checkpoint_diagnostic import (
    CheckpointDiagnosticConfig,
    DiagnosticArm,
    _classify,
    _root_arm,
    run_checkpoint_diagnostic,
)
from go_explore.results import BudgetSummary, TrialSummary
from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.models import GroundedVerification, SnapshotCandidate, SnapshotEvent


def _arm(*, reward: float | None) -> DiagnosticArm:
    return DiagnosticArm(
        name="arm",
        start_state_type="clean",
        job_name="job",
        reward=reward,
        exception_type=None,
        total_tokens=10,
        duration_seconds=1.0,
        status="complete",
        comparable_remaining_cap=True,
    )


def test_classifies_snapshot_transfer_value():
    assert (
        _classify(_arm(reward=0.0), _arm(reward=1.0), _arm(reward=0.0))
        == "snapshot_transfer_value"
    )


def test_classifies_restart_preferred():
    assert (
        _classify(_arm(reward=0.0), _arm(reward=0.0), _arm(reward=1.0))
        == "restart_preferred"
    )


def test_classifies_ties_as_inconclusive():
    assert _classify(_arm(reward=0.0), _arm(reward=0.0), _arm(reward=0.0)) == "inconclusive"


def test_classifies_root_only_and_transferable_state():
    assert (
        _classify(_arm(reward=1.0), _arm(reward=0.0), _arm(reward=0.0))
        == "root_only_progress"
    )
    assert (
        _classify(_arm(reward=1.0), _arm(reward=1.0), _arm(reward=0.0))
        == "state_value_without_transfer_gap"
    )


def test_root_arm_uses_checkpoint_deltas_without_claiming_cap_comparability():
    trial = TrialSummary(
        trial_name="trial",
        task_name="task",
        source=None,
        reward=0.0,
        exception_type=None,
        exception_message=None,
        budget=BudgetSummary(total_tokens=100, duration_seconds=40.0),
    )

    arm = _root_arm(trial, checkpoint_tokens=30, checkpoint_elapsed_seconds=10.0)

    assert arm.total_tokens == 70
    assert arm.duration_seconds == 30.0
    assert arm.status == "observed"
    assert arm.comparable_remaining_cap is False


def test_root_arm_rejects_checkpoint_counter_overrun():
    trial = TrialSummary(
        trial_name="trial",
        task_name="task",
        source=None,
        reward=0.0,
        exception_type=None,
        exception_message=None,
        budget=BudgetSummary(total_tokens=10, duration_seconds=5.0),
    )

    arm = _root_arm(trial, checkpoint_tokens=11, checkpoint_elapsed_seconds=6.0)

    assert arm.status == "unavailable"
    assert arm.total_tokens is None
    assert arm.details == "checkpoint counters exceed final root counters"


def test_dry_run_writes_a_versioned_diagnostic_with_shared_lineage(tmp_path):
    root = tmp_path / "jobs" / "root"
    trial = root / "fix-git__root"
    trial.mkdir(parents=True)
    (root / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(root.parent),
                "environment": {"type": "daytona"},
                "agents": [{"name": "terminus-2", "model_name": "model-a"}],
                "datasets": [{"name": "terminal-bench", "task_names": ["fix-git"]}],
            }
        )
    )
    (root / "result.json").write_text(json.dumps({"n_total_trials": 1}))
    (trial / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "fix-git__root",
                "verifier_result": {"reward": 0.0},
                "agent_result": {"n_input_tokens": 90, "n_output_tokens": 10},
                "started_at": "2026-08-06T00:00:00+00:00",
                "finished_at": "2026-08-06T00:01:00+00:00",
            }
        )
    )
    snapshot_name = "go-explore-fix-git__root-step-1"
    archive = SnapshotArchive(path=root / "archive.json")
    archive.add(
        SnapshotCandidate(
            id="checkpoint",
            event=SnapshotEvent.TEST_RUN,
            restore_ref=snapshot_name,
            metadata={
                "trial_name": "fix-git__root",
                "checkpoint_tokens": 40,
                "checkpoint_elapsed_seconds": 20.0,
            },
            grounded_verification=GroundedVerification(status="failed", tests_passed=2),
        )
    )
    archive.save()

    report = run_checkpoint_diagnostic(
        CheckpointDiagnosticConfig(
            root_job_dir=root,
            snapshot_name=snapshot_name,
            remaining_token_budget=60,
            child_job_name="diagnostic-child",
            clean_job_name="diagnostic-clean",
        )
    )

    assert report.diagnostic_only is True
    assert report.task_name == "fix-git"
    assert report.model == "model-a"
    assert report.checkpoint_cell_key == "<test_run>"
    assert report.root.total_tokens == 60
    assert report.restored_child.start_state_type == "full_snapshot"
    assert report.restored_child.planned_token_cap == 60
    assert report.clean_retry.start_state_type == "clean"
    assert report.clean_retry.planned_token_cap == 60
    assert report.checkpoint_verification == {"status": "failed", "tests_passed": 2, "tests_failed": None, "tests_total": None, "failing_tests": (), "verifier_command": "/tests/test.sh", "timeout_sec": None, "duration_seconds": None, "error": None, "source": "official_preflight"}
    assert json.loads((root / "checkpoint-diagnostic.json").read_text())["diagnostic_only"] is True


def test_config_rejects_empty_or_duplicate_job_names(tmp_path):
    with pytest.raises(ValueError, match="must differ"):
        CheckpointDiagnosticConfig(
            root_job_dir=tmp_path,
            snapshot_name="snapshot",
            remaining_token_budget=1,
            child_job_name="same",
            clean_job_name="same",
        ).validate()
