#!/usr/bin/env bash
set -euo pipefail

TASK="regex-log"
MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
PREFIX="${PREFIX:-phase5-context-ablation-regex-log-20260722}"
ANALYSIS_DIR="${ANALYSIS_DIR:-docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722}"
MANIFEST_PATH="${MANIFEST_PATH:-${ANALYSIS_DIR}/context-ablation-manifest.json}"
ROOT_JOB="${PREFIX}-root-seed-0"
RETRY_JOB="${PREFIX}-retry-seed-0-attempt-0"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$ANALYSIS_DIR"

run_and_continue() {
  echo
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
  set +e
  "$@"
  local status=$?
  set -e
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] exit_code=${status}"
  return 0
}

run_and_continue harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model "$MODEL" \
  --include-task-name "$TASK" \
  --n-tasks 1 \
  --job-name "$RETRY_JOB" \
  --export-traces

run_and_continue harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model "$MODEL" \
  --include-task-name "$TASK" \
  --n-tasks 1 \
  --job-name "$ROOT_JOB" \
  --export-traces

if [[ ! -f "jobs/${ROOT_JOB}/archive.json" ]]; then
  echo "missing archive: jobs/${ROOT_JOB}/archive.json" >&2
  exit 2
fi

export TASK MODEL PREFIX ANALYSIS_DIR MANIFEST_PATH ROOT_JOB RETRY_JOB

SNAPSHOT="$(
  .venv/bin/python - <<'PY'
import os
from pathlib import Path

from go_explore.snapshots.archive import SnapshotArchive

root_job = os.environ["ROOT_JOB"]
archive = SnapshotArchive.load(Path("jobs") / root_job / "archive.json")
selected = archive.select(k=1)
if not selected:
    raise SystemExit("archive has no selectable snapshots")
print(selected[0].snapshot_name)
PY
)"

echo "selected_snapshot=${SNAPSHOT}"

for mode in parent_summary none critical_parent_summary; do
  safe_mode="${mode//_/-}"
  report_path="jobs/${ROOT_JOB}/continuation-report-${mode}.json"
  run_and_continue .venv/bin/python -m go_explore.cli continue-from-snapshots \
    "jobs/${ROOT_JOB}" \
    --snapshot "$SNAPSHOT" \
    --job-prefix "${PREFIX}-${safe_mode}" \
    --context-mode "$mode" \
    --report-path "$report_path" \
    --execute
done

.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

from go_explore.fixed_budget import (
    BUDGET_ENFORCEMENT_DESCRIPTION,
    BUDGET_ENFORCEMENT_PLANNING_ONLY,
)

task = os.environ["TASK"]
model = os.environ["MODEL"]
prefix = os.environ["PREFIX"]
root_job = os.environ["ROOT_JOB"]
retry_job = os.environ["RETRY_JOB"]
archive = json.loads((Path("jobs") / root_job / "archive.json").read_text())
snapshot = archive["entries"][0]["snapshot_name"]
jobs = [
    {
        "method": "retry",
        "role": "retry_attempt",
        "seed": 0,
        "job_name": retry_job,
        "command": [],
        "budget": {
            "token_budget": 20000,
            "budget_fraction": 1.0,
            "enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
            "enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
        },
        "start_state_type": "clean",
        "context_mode": "original_task_only",
        "selector_mode": None,
        "parent_run_id": None,
        "parent_snapshot": None,
        "executor_status": "ready",
    },
    {
        "method": "branch_root",
        "role": "root",
        "seed": 0,
        "job_name": root_job,
        "command": [],
        "budget": {
            "token_budget": 30000,
            "budget_fraction": 1.0,
            "enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
            "enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
        },
        "start_state_type": "clean",
        "context_mode": "original_task_only",
        "selector_mode": "archive_priority",
        "parent_run_id": None,
        "parent_snapshot": None,
        "executor_status": "ready",
    },
]
for mode in ("parent_summary", "none", "critical_parent_summary"):
    safe_mode = mode.replace("_", "-")
    jobs.append(
        {
            "method": f"full_snapshot_{mode}",
            "role": "continuation",
            "seed": 0,
            "job_name": f"{prefix}-{safe_mode}-snapshot-0",
            "command": [],
            "budget": {
                "token_budget": 35000,
                "budget_fraction": 1.0,
                "enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
                "enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
            },
            "start_state_type": "full_snapshot",
            "context_mode": mode,
            "selector_mode": "explicit",
            "parent_run_id": root_job,
            "parent_snapshot": snapshot,
            "executor_status": "ready",
        }
    )
manifest = {
    "schema_version": "go-explore-fixed-budget-plan-v1",
    "experiment_id": "phase5-context-ablation-regex-log-20260722",
    "task_id": task,
    "model": model,
    "budget": {
        "total_token_budget": None,
        "enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
        "enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
    },
    "methods": [job["method"] for job in jobs],
    "seeds": [0],
    "jobs": jobs,
}
path = Path(os.environ["MANIFEST_PATH"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"manifest={path}")
PY

.venv/bin/python -m go_explore.cli build-analysis-tables \
  --manifest "$MANIFEST_PATH" \
  --job-dir "jobs/${RETRY_JOB}" \
  --job-dir "jobs/${ROOT_JOB}" \
  --job-dir "jobs/${PREFIX}-parent-summary-snapshot-0" \
  --job-dir "jobs/${PREFIX}-none-snapshot-0" \
  --job-dir "jobs/${PREFIX}-critical-parent-summary-snapshot-0" \
  --continuation-report "jobs/${ROOT_JOB}/continuation-report-parent_summary.json" \
  --continuation-report "jobs/${ROOT_JOB}/continuation-report-none.json" \
  --continuation-report "jobs/${ROOT_JOB}/continuation-report-critical_parent_summary.json" \
  --event-log "jobs/${ROOT_JOB}/events.jsonl" \
  --output-dir "$ANALYSIS_DIR"

echo "analysis_dir=${ANALYSIS_DIR}"
