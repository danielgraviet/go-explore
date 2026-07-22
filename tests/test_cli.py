from __future__ import annotations

import argparse
import json
from pathlib import Path

from go_explore.cli import (
    continue_from_snapshots,
    plan_fixed_budget,
    plan_start_state_baselines_cmd,
    run_experiment_cmd,
)
from go_explore.events import EVENT_LOG_FILENAME
from go_explore.snapshots.archive import ARCHIVE_FILENAME, SnapshotArchive
from go_explore.snapshots.models import SnapshotCandidate, SnapshotEvent


def _write_root_job(job_dir: Path) -> None:
    trial_dir = job_dir / "fix-git__root"
    trial_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(job_dir.parent),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": "terminus-2",
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
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "fix-git__root",
                "task_name": "fix-git",
                "verifier_result": {"reward": 0.0},
            }
        )
    )


def _candidate(
    *,
    changed_files: tuple[str, ...],
    event: SnapshotEvent,
    restore_ref: str,
) -> SnapshotCandidate:
    return SnapshotCandidate(
        id=f"fix-git__root:{restore_ref}",
        event=event,
        restore_ref=restore_ref,
        changed_files=changed_files,
        metadata={"trial_name": "fix-git__root", "step_id": "0"},
    )


def test_continue_from_snapshots_uses_configured_archive_selector(
    tmp_path,
    capsys,
):
    root_job_dir = tmp_path / "jobs" / "root"
    root_job_dir.mkdir(parents=True)
    _write_root_job(root_job_dir)

    archive = SnapshotArchive(path=root_job_dir / ARCHIVE_FILENAME)
    archive.add(
        _candidate(
            changed_files=("low.py",),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-low",
        )
    )
    archive.add(
        _candidate(
            changed_files=("high.py",),
            event=SnapshotEvent.TEST_RUN,
            restore_ref="snap-high",
        )
    )
    archive.save()

    labels_path = tmp_path / "oracle-labels.json"
    labels_path.write_text(json.dumps({"snap-low": 1.0, "snap-high": 0.0}))

    exit_code = continue_from_snapshots(
        argparse.Namespace(
            root_job_dir=root_job_dir,
            trial_name=None,
            snapshot=[],
            snapshot_prefix="go-explore",
            from_archive=True,
            selector_mode="oracle",
            selector_seed=None,
            oracle_labels=labels_path,
            archive_path=None,
            job_prefix="cont",
            max_snapshots=1,
            agent=None,
            model=None,
            extra_arg=[],
            context_mode="parent_summary",
            report_path=None,
            execute=False,
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "mode=oracle" in stdout
    assert "snapshot_template_name=snap-low" in stdout
    assert "snapshot_template_name=snap-high" not in stdout

    events = [
        json.loads(line)
        for line in (root_job_dir / EVENT_LOG_FILENAME).read_text().splitlines()
    ]
    assert events[-1]["event_type"] == "snapshot_selected"
    assert events[-1]["snapshot_name"] == "snap-low"
    assert events[-1]["selector_mode"] == "oracle"
    assert events[-1]["selector_reasons"] == ["oracle_label=1"]
    assert events[-1]["cell_key"] == "{low.py}"


def test_plan_start_state_baselines_command_writes_manifest(tmp_path, capsys):
    root_job_dir = tmp_path / "jobs" / "root"
    root_job_dir.mkdir(parents=True)
    _write_root_job(root_job_dir)
    manifest_path = tmp_path / "plans" / "claim1.json"
    diff_path = tmp_path / "artifacts" / "parent.diff"

    exit_code = plan_start_state_baselines_cmd(
        argparse.Namespace(
            root_job_dir=root_job_dir,
            trial_name=None,
            start_state_type=["clean", "diff_only", "full_snapshot"],
            snapshot=["snapshot-a"],
            from_archive=False,
            selector_mode="archive_priority",
            selector_seed=None,
            oracle_labels=None,
            archive_path=None,
            diff_path=diff_path,
            manifest_path=manifest_path,
            job_prefix="claim1",
            max_snapshots=1,
            agent=None,
            model=None,
            extra_arg=[],
            clean_context_mode="original_task_only",
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "clean\toriginal_task_only\tready\tclaim1-clean" in stdout
    assert "diff_only\toriginal_task_only\tmanifest_only\tclaim1-diff-only" in stdout
    assert "full_snapshot\tparent_summary\tready\tclaim1-full-snapshot-0" in stdout

    data = json.loads(manifest_path.read_text())
    assert [plan["start_state_type"] for plan in data["plans"]] == [
        "clean",
        "diff_only",
        "full_snapshot",
    ]
    assert data["plans"][1]["parent_artifacts"] == [str(diff_path)]
    assert data["plans"][1]["executor_status"] == "manifest_only"
    assert data["plans"][2]["parent_snapshot"] == "snapshot-a"


def test_plan_start_state_baselines_command_can_plan_clean_parent_summary(
    tmp_path,
    capsys,
):
    root_job_dir = tmp_path / "jobs" / "root"
    root_job_dir.mkdir(parents=True)
    _write_root_job(root_job_dir)
    manifest_path = tmp_path / "plans" / "claim1.json"
    parent_context_path = (
        root_job_dir / "fix-git__root" / "agent" / "trajectory.json"
    )

    exit_code = plan_start_state_baselines_cmd(
        argparse.Namespace(
            root_job_dir=root_job_dir,
            trial_name=None,
            start_state_type=["clean"],
            snapshot=[],
            from_archive=False,
            selector_mode="archive_priority",
            selector_seed=None,
            oracle_labels=None,
            archive_path=None,
            diff_path=None,
            manifest_path=manifest_path,
            job_prefix="claim1",
            max_snapshots=None,
            agent=None,
            model=None,
            extra_arg=[],
            clean_context_mode="parent_summary",
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "clean\tparent_summary\tready\tclaim1-clean" in stdout
    assert "snapshot_template_name=" not in stdout

    data = json.loads(manifest_path.read_text())
    plan = data["plans"][0]
    assert plan["parent_snapshot"] is None
    assert plan["start_state_type"] == "clean"
    assert plan["context_mode"] == "parent_summary"
    assert plan["parent_artifacts"] == [str(parent_context_path)]
    assert "context_mode=parent_summary" in plan["command"]
    assert f"parent_context_path={parent_context_path}" in plan["command"]


def test_plan_fixed_budget_command_writes_manifest(tmp_path, capsys):
    manifest_path = tmp_path / "plans" / "fixed-budget.json"

    exit_code = plan_fixed_budget(
        argparse.Namespace(
            dataset="terminal-bench@2.0",
            path=None,
            jobs_dir=Path("jobs"),
            task_name="fix-git",
            env="daytona",
            model="model-a",
            agent=None,
            agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
            extra_arg=[],
            experiment_id="pilot-1",
            job_prefix="pilot",
            manifest_path=manifest_path,
            total_token_budget=100_000,
            method=["single", "retry", "random_branch"],
            seed=[5],
            n_retries=2,
            n_branch_continuations=1,
            branch_root_fraction=0.25,
            branch_context_mode="critical_parent_summary",
            snapshot=["snapshot-a"],
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert f"manifest: {manifest_path}" in stdout
    assert "budget_enforcement: planning_only" in stdout
    assert "not stopped when a job reaches this value" in stdout
    assert (
        "single\tsingle\tseed=5\tplanned_budget=100000\t"
        "enforcement=planning_only\tready\tpilot-single-seed-5"
    ) in stdout
    assert (
        "retry\tretry_attempt\tseed=5\tplanned_budget=50000\t"
        "enforcement=planning_only\tready"
    ) in stdout
    assert (
        "random_branch\troot\tseed=5\tplanned_budget=25000\t"
        "enforcement=planning_only\tready"
    ) in stdout

    data = json.loads(manifest_path.read_text())
    assert data["schema_version"] == "go-explore-fixed-budget-plan-v1"
    assert data["experiment_id"] == "pilot-1"
    assert data["budget"]["enforcement"] == "planning_only"
    assert "not stopped" in data["budget"]["enforcement_description"]
    assert data["methods"] == ["single", "retry", "random_branch"]
    assert data["seeds"] == [5]
    assert data["jobs"][-1]["parent_snapshot"] == "snapshot-a"
    assert data["jobs"][-1]["budget"]["token_budget"] == 75_000
    assert data["jobs"][-1]["context_mode"] == "critical_parent_summary"
    assert "context_mode=critical_parent_summary" in data["jobs"][-1]["command"]


def test_run_experiment_command_dry_run_writes_manifest(tmp_path, capsys):
    manifest_path = tmp_path / "plans" / "experiment.json"
    analysis_dir = tmp_path / "analysis"

    exit_code = run_experiment_cmd(
        argparse.Namespace(
            dataset="terminal-bench@2.0",
            path=None,
            jobs_dir=tmp_path / "jobs",
            task_name="fix-git",
            env="daytona",
            model="model-a",
            agent=None,
            agent_import_path=None,
            extra_arg=[],
            experiment_id="exp-1",
            job_prefix="exp",
            manifest_path=manifest_path,
            analysis_dir=analysis_dir,
            total_token_budget=100_000,
            method=["single", "promising_branch"],
            seed=[0],
            n_retries=2,
            n_branch_continuations=1,
            branch_root_fraction=0.3,
            branch_context_mode="parent_summary",
            execute=False,
            rerun_existing=False,
            no_analysis=False,
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert f"manifest: {manifest_path}" in stdout
    assert "budget_enforcement: planning_only" in stdout
    assert "not stopped when a job reaches this value" in stdout
    assert "single\tsingle\tplanned\texp-single-seed-0" in stdout
    assert "promising_branch\troot\tplanned\texp-promising-branch-seed-0-root" in stdout
    assert (
        "promising_branch\tcontinuation\tplanned_after_root_archive"
        "\texp-promising-branch-seed-0-cont-0"
    ) in stdout
    assert "go_explore.agents.factory:SnapshotAwareTerminus2" in stdout

    data = json.loads(manifest_path.read_text())
    assert data["methods"] == ["single", "promising_branch"]
    assert not (analysis_dir / "run-summary.csv").exists()
