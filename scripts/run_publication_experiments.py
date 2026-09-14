"""Run Claim 1 / recovery / env-progress experiments while staying under Daytona's 100-snapshot cap.

Roots snapshot with GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT=4. Retries and children
use snapshot_policy=none. Checkpoints stay on the account after each seed
unless `--prune` is passed. Abort if live snapshots hit 90.

Env-search stages start retry and branch roots from the planted warehouse
snapshot. Do not `--prune` that plant while later seeds still need it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from daytona import AsyncDaytona

from go_explore.experiment_runner import (
    RunExperimentConfig,
    format_run_experiment_report,
    run_fixed_budget_experiment,
)
from go_explore.env_progress import (
    CHECKPOINT_JOB_NAME,
    ENV_PROGRESS_ARMS,
    PLANT_TRIAL_NAME,
    TASK_DIR,
    WAREHOUSE_LOT,
)
from go_explore.harbor import HarborRunConfig
from go_explore.representation_ablation import (
    RepresentationAblationConfig,
    run_representation_ablation,
)
from go_explore.results import summarize_job
from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.backends import daytona_snapshot_name
from go_explore.snapshots.capture_diff import (
    assert_parent_diff_artifact,
    capture_parent_diff,
    parse_prebuilt_image,
)

REPO = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO / "jobs"
CAP_SOFT = 70
CAP_HARD = 90
ROOT_BUDGET = 300_000
CHILD_BUDGET = 200_000
RECOVERY_BUDGET = 1_000_000
ENV_SEARCH_BUDGET = 600_000
RETENTION = "4"
MODEL = "anthropic/claude-haiku-4-5-20251001"
AGENT = "go_explore.agents.factory:SnapshotAwareTerminus2"


def _load_env() -> None:
    env_path = REPO / ".env"
    if not env_path.exists():
        raise SystemExit("Missing .env with DAYTONA_API_KEY and ANTHROPIC_API_KEY")
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    os.environ["PYTHONPATH"] = f"{REPO}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"
    os.environ["GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT"] = RETENTION
    os.environ["PATH"] = f"{Path.home() / '.local' / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"


async def snapshot_count() -> tuple[int, int]:
    async with AsyncDaytona() as daytona:
        page = await daytona.snapshot.list(limit=200)
        total = len(page.items)
        go_explore = len([s for s in page.items if s.name.startswith("go-explore-")])
        return total, go_explore


PRUNE_AFTER_SEED = False


def prune() -> None:
    subprocess.run(
        [sys.executable, str(REPO / "prune_snapshots.py"), "--n-branch-continuations", "2"],
        cwd=REPO,
        check=False,
    )


def maybe_prune() -> None:
    if not PRUNE_AFTER_SEED:
        return
    print("pruning go-explore snapshots after seed")
    prune()


def guard_cap(label: str) -> tuple[int, int]:
    total, go_explore = asyncio.run(snapshot_count())
    print(f"snapshots before {label}: total={total} go-explore={go_explore}")
    if total >= CAP_SOFT:
        print(
            f"warning: snapshot count {total} is at the soft cap {CAP_SOFT}; "
            "not pruning (pass --prune to delete finished go-explore snapshots)"
        )
    if total >= CAP_HARD:
        raise SystemExit(
            f"abort {label}: {total} snapshots on account (hard cap {CAP_HARD})"
        )
    return total, go_explore


def _base_config(task_name: str) -> HarborRunConfig:
    return HarborRunConfig(
        jobs_dir=JOBS_DIR,
        agent=None,
        agent_import_path=AGENT,
        env="daytona",
        dataset="terminal-bench@2.0",
        model=MODEL,
        task_name=task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        export_traces=True,
    )


def choose_checkpoint(root_job_dir: Path) -> str:
    archive = SnapshotArchive.load(root_job_dir / "archive.json")
    ranked = sorted(
        (entry for entry in archive.entries() if entry.remote_retained),
        key=lambda entry: (entry.priority, entry.score),
        reverse=True,
    )
    for entry in ranked:
        if entry.event == "verifier" and entry.tests_passed is None:
            continue
        return entry.snapshot_name
    if ranked:
        return ranked[0].snapshot_name
    raise SystemExit(f"no retained snapshot in {root_job_dir / 'archive.json'}")


def run_claim1_seed(task_name: str, seed: int) -> None:
    label = f"claim1 {task_name} seed {seed}"
    guard_cap(label)
    experiment_id = f"claim1-{task_name}-seed-{seed}"
    job_prefix = f"claim1-{task_name}"
    analysis_dir = (
        REPO
        / "docs/experiments/main-benchmark/analysis"
        / experiment_id
    )
    report = run_fixed_budget_experiment(
        RunExperimentConfig(
            experiment_id=experiment_id,
            base_config=_base_config(task_name),
            total_token_budget=ROOT_BUDGET,
            methods=("single",),
            seeds=(seed,),
            job_prefix=job_prefix,
            manifest_path=REPO
            / "docs/experiments/main-benchmark/manifests"
            / f"{experiment_id}.json",
            analysis_dir=analysis_dir,
            execute=True,
        )
    )
    print(format_run_experiment_report(report))
    root_job_dir = JOBS_DIR / f"{job_prefix}-single-seed-{seed}"
    if not (root_job_dir / "archive.json").exists():
        raise SystemExit(f"root {root_job_dir} has no archive.json")
    snapshot_name = choose_checkpoint(root_job_dir)
    print(f"checkpoint: {snapshot_name}")
    diff_path = root_job_dir / "parent.diff"
    baseline_image = parse_prebuilt_image(
        (root_job_dir / "job.log").read_text(errors="replace")
        if (root_job_dir / "job.log").exists()
        else ""
    )
    asyncio.run(
        capture_parent_diff(
            snapshot_name,
            diff_path,
            baseline_image=baseline_image,
        )
    )
    print(
        f"parent.diff bytes={diff_path.stat().st_size} "
        f"baseline_image={baseline_image or 'none'}"
    )
    assert_parent_diff_artifact(diff_path)
    ablation = run_representation_ablation(
        RepresentationAblationConfig(
            root_job_dir=root_job_dir,
            snapshot_name=snapshot_name,
            remaining_token_budget=CHILD_BUDGET,
            job_prefix=f"{job_prefix}-seed-{seed}-claim1",
            diff_path=diff_path,
            output_path=root_job_dir / "representation-ablation.json",
            execute=True,
        )
    )
    print(json.dumps(ablation.to_json_dict(), indent=2)[:2000])
    maybe_prune()


def run_recovery_seed(task_name: str, seed: int) -> None:
    label = f"recovery {task_name} seed {seed}"
    guard_cap(label)
    experiment_id = f"recovery-{task_name}-seed-{seed}"
    report = run_fixed_budget_experiment(
        RunExperimentConfig(
            experiment_id=experiment_id,
            base_config=_base_config(task_name),
            total_token_budget=RECOVERY_BUDGET,
            methods=("retry", "promising_branch"),
            seeds=(seed,),
            job_prefix=f"recovery-{task_name}",
            manifest_path=REPO
            / "docs/experiments/main-benchmark/manifests"
            / f"{experiment_id}.json",
            analysis_dir=REPO
            / "docs/experiments/main-benchmark/analysis"
            / experiment_id,
            n_retries=3,
            n_branch_continuations=2,
            branch_root_fraction=0.3,
            branch_context_mode="none",
            execute=True,
            skip_if_root_solved=True,
        )
    )
    print(format_run_experiment_report(report))
    maybe_prune()


def _plant_mod():
    import importlib.util

    path = Path(__file__).resolve().parent / "plant_env_progress_checkpoint.py"
    spec = importlib.util.spec_from_file_location("plant_env_progress_checkpoint", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env_checkpoint_dir() -> Path:
    return JOBS_DIR / CHECKPOINT_JOB_NAME


def env_ablation_path(seed: int) -> Path:
    return env_checkpoint_dir() / f"representation-ablation-seed-{seed}.json"


def planted_snapshot_name() -> str:
    return daytona_snapshot_name(f"{PLANT_TRIAL_NAME}-step-0")


async def snapshot_is_live(name: str) -> bool:
    async with AsyncDaytona() as daytona:
        page = await daytona.snapshot.list(limit=200)
        return any(item.name == name for item in page.items)


def ensure_env_progress_checkpoint() -> Path:
    root = env_checkpoint_dir()
    snapshot_name = planted_snapshot_name()
    live = asyncio.run(snapshot_is_live(snapshot_name))
    if (
        live
        and (root / "archive.json").exists()
        and (root / "parent.diff").exists()
        and (root / "config.json").exists()
    ):
        print(f"reusing planted checkpoint {root} snapshot={snapshot_name}")
        return root
    guard_cap("env-progress plant")
    plant = _plant_mod()
    print(f"planting checkpoint {snapshot_name} from Dockerfile")
    return asyncio.run(
        plant.plant_checkpoint(
            jobs_dir=JOBS_DIR,
            model=MODEL,
            agent_import_path=AGENT,
        )
    )


def _arm_cell(arm) -> str:
    exception = arm.exception_type or ""
    if "DiffApply" in exception:
        return "DiffApplyFailed"
    if "Budget" in exception:
        return "budget"
    if exception:
        return exception
    if arm.reward == 1.0:
        return "1.0"
    if arm.reward == 0.0:
        return "0.0"
    if arm.reward is None:
        return "planned"
    return str(arm.reward)


def check_env_progress_inclusion(root: Path, snapshot_name: str, report) -> None:
    diff_text = (root / "parent.diff").read_text(errors="replace")
    if WAREHOUSE_LOT in diff_text:
        raise SystemExit("inclusion failed: lot code leaked into parent.diff")
    snap_plans = [
        plan for plan in report.plans if plan["start_state_type"] == "full_snapshot"
    ]
    if not snap_plans:
        raise SystemExit("inclusion failed: no full_snapshot plan")
    command = " ".join(snap_plans[0]["command"])
    if f"snapshot_template_name={snapshot_name}" not in command:
        raise SystemExit(
            f"inclusion failed: snapshot arm missing restore ref {snapshot_name}"
        )
    by_name = {arm.start_state_type: arm for arm in report.arms}
    diff_arm = by_name.get("diff_only")
    if diff_arm is not None and diff_arm.reward == 1.0:
        raise SystemExit(
            "inclusion failed: diff_only recovered the lot; stop and report"
        )
    print(
        "inclusion: parent.diff has no lot; "
        f"snapshot restore ref present; diff_only={_arm_cell(diff_arm) if diff_arm else 'missing'}"
    )


def run_env_progress_seed(seed: int, *, inclusion: bool) -> None:
    label = f"env-progress seed {seed}"
    guard_cap(label)
    root = ensure_env_progress_checkpoint()
    snapshot_name = planted_snapshot_name()
    output_path = env_ablation_path(seed)
    ablation = run_representation_ablation(
        RepresentationAblationConfig(
            root_job_dir=root,
            snapshot_name=snapshot_name,
            remaining_token_budget=CHILD_BUDGET,
            job_prefix=f"env-progress-seed-{seed}",
            diff_path=root / "parent.diff",
            output_path=output_path,
            execute=True,
            include_arms=ENV_PROGRESS_ARMS,
        )
    )
    print(json.dumps(ablation.to_json_dict(), indent=2)[:3000])
    cells = {arm.start_state_type: _arm_cell(arm) for arm in ablation.arms}
    print(
        f"seed {seed}: clean={cells.get('clean')} "
        f"diff_only={cells.get('diff_only')} "
        f"full_snapshot={cells.get('full_snapshot')}"
    )
    if inclusion:
        check_env_progress_inclusion(root, snapshot_name, ablation)
    maybe_prune()


def env_search_analysis_dir(seed: int) -> Path:
    return (
        REPO
        / "docs/experiments/main-benchmark/analysis"
        / f"env-search-seed-{seed}"
    )


def env_search_base_config(snapshot_name: str) -> HarborRunConfig:
    return HarborRunConfig(
        jobs_dir=JOBS_DIR,
        agent=None,
        agent_import_path=AGENT,
        env="daytona",
        path=TASK_DIR,
        model=MODEL,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        export_traces=False,
        environment_kwargs=(f"snapshot_template_name={snapshot_name}",),
    )


def _job_solved(job_dir: Path | None) -> bool:
    if job_dir is None or not (job_dir / "result.json").exists():
        return False
    return any(trial.succeeded for trial in summarize_job(job_dir).trials)


def env_search_outcomes(seed: int) -> dict[str, bool | str]:
    report_path = env_search_analysis_dir(seed) / "execution-report.json"
    report = json.loads(report_path.read_text())
    retry_solved = False
    root_solved = False
    child_solved = False
    children_launched = False
    skipped_root_solved = False
    for record in report["records"]:
        role = record.get("role")
        status = record.get("status")
        job_dir = Path(record["job_dir"]) if record.get("job_dir") else None
        if status == "skipped_root_solved":
            skipped_root_solved = True
            continue
        solved = _job_solved(job_dir)
        if record.get("method") == "retry":
            retry_solved = retry_solved or solved
        elif role == "root":
            root_solved = solved
        elif role == "continuation":
            children_launched = True
            child_solved = child_solved or solved
    rescued = (not root_solved) and child_solved
    return {
        "retry_solved": retry_solved,
        "root_solved": root_solved,
        "children_launched": children_launched and not skipped_root_solved,
        "child_solved": child_solved,
        "rescued": rescued,
        "branch_solved": root_solved or child_solved,
        "skipped_root_solved": skipped_root_solved,
    }


def assert_env_search_planted_start(report, snapshot_name: str) -> None:
    checked = 0
    for record in report.records:
        if record.role not in {"retry_attempt", "root"}:
            continue
        command = " ".join(record.command)
        if f"snapshot_template_name={snapshot_name}" not in command:
            raise SystemExit(
                f"inclusion failed: {record.job_name} missing plant restore "
                f"{snapshot_name}"
            )
        if "--path" not in record.command:
            raise SystemExit(
                f"inclusion failed: {record.job_name} did not use --path"
            )
        if "--agent" in record.command:
            raise SystemExit(
                f"inclusion failed: {record.job_name} set --agent as well as "
                "the snapshot-aware import path"
            )
        checked += 1
    if checked < 4:
        raise SystemExit(
            f"inclusion failed: expected 3 retries and 1 root with plant start, "
            f"checked {checked}"
        )
    print(f"inclusion: plant restore {snapshot_name} on {checked} retry/root jobs")


def env_search_is_dual_ceiling(seed: int) -> bool:
    report_path = env_search_analysis_dir(seed) / "execution-report.json"
    if not report_path.exists():
        return False
    outcomes = env_search_outcomes(seed)
    return bool(outcomes["retry_solved"] and outcomes["branch_solved"])


def run_env_search_seed(seed: int, *, inclusion: bool) -> None:
    label = f"env-search seed {seed}"
    guard_cap(label)
    ensure_env_progress_checkpoint()
    snapshot_name = planted_snapshot_name()
    if not asyncio.run(snapshot_is_live(snapshot_name)):
        raise SystemExit(f"plant snapshot {snapshot_name} is not live")
    experiment_id = f"env-search-seed-{seed}"
    report = run_fixed_budget_experiment(
        RunExperimentConfig(
            experiment_id=experiment_id,
            base_config=env_search_base_config(snapshot_name),
            total_token_budget=ENV_SEARCH_BUDGET,
            methods=("retry", "promising_branch"),
            seeds=(seed,),
            job_prefix="env-search",
            manifest_path=REPO
            / "docs/experiments/main-benchmark/manifests"
            / f"{experiment_id}.json",
            analysis_dir=env_search_analysis_dir(seed),
            n_retries=3,
            n_branch_continuations=2,
            branch_root_fraction=0.3,
            branch_context_mode="none",
            execute=True,
            skip_if_root_solved=True,
        )
    )
    print(format_run_experiment_report(report))
    if inclusion:
        assert_env_search_planted_start(report, snapshot_name)
    if report.has_infrastructure_failures:
        raise SystemExit(
            f"abort {label}: infrastructure failures; rerun the canary. "
            "Do not invent a harder task because a job crashed."
        )
    outcomes = env_search_outcomes(seed)
    print(
        f"seed {seed}: retry_solved={outcomes['retry_solved']} "
        f"root_solved={outcomes['root_solved']} "
        f"children_launched={outcomes['children_launched']} "
        f"child_solved={outcomes['child_solved']} "
        f"rescued={outcomes['rescued']} "
        f"branch_solved={outcomes['branch_solved']}"
    )
    maybe_prune()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=(
            "a-canary",
            "a",
            "b-canary",
            "b",
            "env-canary",
            "env",
            "env-search-canary",
            "env-search",
            "count",
        ),
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete finished go-explore snapshots after each seed.",
    )
    args = parser.parse_args()
    global PRUNE_AFTER_SEED
    PRUNE_AFTER_SEED = args.prune
    os.chdir(REPO)
    _load_env()
    os.environ["PYTHONUNBUFFERED"] = "1"
    if args.stage == "count":
        total, go_explore = asyncio.run(snapshot_count())
        print(f"total={total} go-explore={go_explore}")
        return 0
    if args.stage == "a-canary":
        run_claim1_seed("extract-elf", 0)
        return 0
    if args.stage == "a":
        for task in ("extract-elf", "regex-log"):
            for seed in range(5):
                root = JOBS_DIR / f"claim1-{task}-single-seed-{seed}"
                if (root / "representation-ablation.json").exists():
                    print(f"skip claim1 {task} seed {seed}: already complete")
                    continue
                run_claim1_seed(task, seed)
        return 0
    if args.stage == "b-canary":
        run_recovery_seed("extract-elf", 0)
        return 0
    if args.stage == "b":
        for task in ("extract-elf", "regex-log"):
            for seed in range(8):
                analysis = (
                    REPO
                    / "docs/experiments/main-benchmark/analysis"
                    / f"recovery-{task}-seed-{seed}"
                )
                if (analysis / "execution-report.json").exists():
                    print(f"skip recovery {task} seed {seed}: already complete")
                    continue
                run_recovery_seed(task, seed)
        return 0
    if args.stage == "env-canary":
        run_env_progress_seed(0, inclusion=True)
        return 0
    if args.stage == "env":
        for seed in range(5):
            if env_ablation_path(seed).exists():
                print(f"skip env-progress seed {seed}: already complete")
                continue
            run_env_progress_seed(seed, inclusion=(seed == 0))
        return 0
    if args.stage == "env-search-canary":
        run_env_search_seed(0, inclusion=True)
        if env_search_is_dual_ceiling(0):
            print(
                "dual-ceiling: retry and promising_branch both solved seed 0 "
                "from the planted snapshot. Stop. Do not run scored seeds."
            )
        return 0
    if args.stage == "env-search":
        canary_report = env_search_analysis_dir(0) / "execution-report.json"
        if canary_report.exists() and env_search_is_dual_ceiling(0):
            print(
                "dual-ceiling stop: seed 0 both methods solved from the plant. "
                "Not running seeds 1-4."
            )
            return 0
        for seed in range(5):
            if (env_search_analysis_dir(seed) / "execution-report.json").exists():
                print(f"skip env-search seed {seed}: already complete")
                continue
            run_env_search_seed(seed, inclusion=(seed == 0))
            if seed == 0 and env_search_is_dual_ceiling(0):
                print(
                    "dual-ceiling: retry and promising_branch both solved "
                    "seed 0 from the planted snapshot. Stop."
                )
                return 0
        return 0
    raise SystemExit(f"unknown stage {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
