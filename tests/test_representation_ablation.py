import json

from go_explore.representation_ablation import (
    CLAIM1_ARMS,
    RepresentationAblationConfig,
    run_representation_ablation,
)
from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.models import SnapshotCandidate, SnapshotEvent


def _write_root_job(tmp_path):
    root = tmp_path / "jobs" / "root"
    trial = root / "fix-git__root"
    agent_dir = trial / "agent"
    agent_dir.mkdir(parents=True)
    (root / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(root.parent),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": None,
                        "import_path": "go_explore.agents.factory:SnapshotAwareTerminus2",
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
    (root / "result.json").write_text(json.dumps({"n_total_trials": 1}))
    (trial / "result.json").write_text(
        json.dumps(
            {
                "trial_name": "fix-git__root",
                "task_name": "fix-git",
                "verifier_result": {"reward": 0.0},
                "agent_result": {"n_input_tokens": 90, "n_output_tokens": 10},
            }
        )
    )
    (agent_dir / "trajectory.json").write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "step_id": 1,
                        "source": "agent",
                        "tool_calls": [
                            {
                                "function_name": "bash_command",
                                "arguments": {
                                    "keystrokes": "pip install requests\n"
                                },
                            }
                        ],
                        "observation": {
                            "results": [{"content": "Successfully installed"}]
                        },
                    }
                ]
            }
        )
    )
    (root / "parent.diff").write_text("diff --git a/x b/x\n")
    snapshot_name = "go-explore-fix-git__root-step-1"
    archive = SnapshotArchive(path=root / "archive.json")
    archive.add(
        SnapshotCandidate(
            id="checkpoint",
            event=SnapshotEvent.TEST_RUN,
            restore_ref=snapshot_name,
            metadata={"trial_name": "fix-git__root", "step_id": "1"},
        )
    )
    archive.save()
    return root, snapshot_name


def test_representation_ablation_plans_five_equal_cap_arms(tmp_path):
    root, snapshot_name = _write_root_job(tmp_path)

    report = run_representation_ablation(
        RepresentationAblationConfig(
            root_job_dir=root,
            snapshot_name=snapshot_name,
            remaining_token_budget=200_000,
            job_prefix="claim1",
        )
    )

    assert report.diagnostic_only is True
    assert report.schema_version == "go-explore-claim1-ablation-v1"
    assert len(report.arms) == len(CLAIM1_ARMS)
    assert {arm.planned_token_cap for arm in report.arms} == {200_000}
    start_states = [arm.start_state_type for arm in report.arms]
    assert start_states == [
        "clean",
        "diff_only",
        "diff_only",
        "command_replay",
        "full_snapshot",
    ]
    snapshot_plan = next(
        plan for plan in report.plans if plan["start_state_type"] == "full_snapshot"
    )
    assert snapshot_plan["parent_snapshot"] == snapshot_name
    assert snapshot_plan["context_mode"] == "none"
    assert "token_budget=200000" in " ".join(snapshot_plan["command"])
    assert "snapshot_policy=none" in " ".join(snapshot_plan["command"])
    payload = json.loads((root / "representation-ablation.json").read_text())
    assert payload["remaining_token_budget"] == 200_000
    assert payload["diagnostic_only"] is True
