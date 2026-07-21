from __future__ import annotations

import argparse
import json
from pathlib import Path

from go_explore.cli import continue_from_snapshots, plan_start_state_baselines_cmd
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
