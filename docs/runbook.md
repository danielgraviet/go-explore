# Runbook

Use this page to verify the project before and after changes.

## Prereqs

- Python env managed by `uv`.
- Harbor installed and available as `harbor`: need version 0.19.0 with the `daytona` and `huggingface` extras.
- Docker running for local Docker Harbor runs.
- `.env` with Daytona/model credentials for Daytona or model-backed runs.

E2E tests and live Harbor runs may call Harbor, Docker, Daytona, and model APIs. Do not treat them as required for every code change.

## Cheap Checks

Run normal tests through the checked-in virtualenv when it exists. This avoids
`uv` touching the user-level cache path, which can be blocked by sandboxed
agents:

```bash
.venv/bin/python -m pytest -v
```

Run a focused file while developing:

```bash
.venv/bin/python -m pytest tests/test_harbor.py -q
```

Use `uv run ...` only when you intentionally need `uv` to create or update the
environment. If `uv` fails with a cache permission error, either use the venv
command above or set `UV_CACHE_DIR=/private/tmp/go-explore-uv-cache`.

## E2E Checks

Run e2e tests explicitly:

```bash
.venv/bin/python -m pytest -v -k e2e
```

Or:

```bash
.venv/bin/python -m pytest --run-e2e -s
```

E2E tests are skipped by default unless `--run-e2e` is passed or `-k e2e` is used.

## Local Docker Oracle Smoke

Print the command first:

```bash
python3 -m go_explore.cli oracle-run \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 1 \
  --n-concurrent 1 \
  --job-name oracle-smoke
```

## NOTE

Make sure your virtual environment is activated by running source .venv/bin/activate

Run it:

```bash
python3 -m go_explore.cli oracle-run \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 1 \
  --n-concurrent 1 \
  --job-name oracle-smoke \
  --execute
```

This verifies Harbor can resolve Terminal-Bench and run locally through Docker.

## Daytona Oracle Smoke

Load credentials, then run an oracle task in Daytona:

```bash
set -a; source .env; set +a
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
harbor run \
  --agent oracle \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 1 \
  --job-name daytona-oracle-smoke \
  --export-traces
```

This verifies Harbor can create and score a Daytona task environment.

## Daytona Terminus Snapshot Smoke

Run a real agent through the snapshot-aware wrapper:

```bash
set -a; source .env; set +a
harbor run \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name fix-git \
  --job-name daytona-terminus-snapshot-smoke \
  --export-traces \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2
```

Do not pass `--agent terminus-2` with this command. Harbor will use the built-in agent and skip the import-path wrapper. Use `--agent-import-path` for the wrapper so Harbor's ATIF exporter records the underlying Terminus-2 agent metadata correctly.

## Fixed-Budget Smoke Experiments

Use this workflow to run the cheap smoke benchmark tasks from
`docs/experiments/main-benchmark/manifests/smoke/`. Start with one task and one
job. Do not launch the whole manifest until the first completed job has a sane
cost and artifact shape.

Recommended first task:

- `regex-log`, representative medium task.
- `fix-git`, cheapest known harness canary, but too easy for evidence.

Load credentials and local imports:

```bash
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"
```

Inspect planned jobs for one smoke task:

```bash
python3 - <<'PY'
import json

manifest = json.load(open("docs/experiments/main-benchmark/manifests/smoke/regex-log.json"))
for job in manifest["jobs"]:
    print(
        job["method"],
        job["role"],
        job["executor_status"],
        job["job_name"],
    )
PY
```

Run only the single clean run first:

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name regex-log \
  --n-tasks 1 \
  --job-name phase4-smoke-regex-log-single-seed-0 \
  --export-traces
```

Do not start retry jobs until this single run finishes and you have inspected
cost, duration, and snapshot overhead. If you interrupt Harbor with `Ctrl-C`,
the job directory may contain partial artifacts and `result.json` may still say
`n_running_trials: 1`; treat that as an interrupted run, not a completed result.

Summarize the completed job:

```bash
uv run python -m go_explore.cli summarize-job \
  jobs/phase4-smoke-regex-log-single-seed-0
```

Inspect the snapshot artifacts:

```bash
python3 -m json.tool jobs/phase4-smoke-regex-log-single-seed-0/archive.json
tail -20 jobs/phase4-smoke-regex-log-single-seed-0/events.jsonl
```

For branch methods, run roots before continuations:

```bash
uv run python -m go_explore.cli run-experiment \
  --dataset terminal-bench@2.0 \
  --task-name regex-log \
  --experiment-id phase4-smoke-regex-log-001 \
  --job-prefix phase4-smoke-regex-log \
  --model anthropic/claude-haiku-4-5-20251001 \
  --total-token-budget 100000 \
  --method single \
  --method retry \
  --method random_branch \
  --method promising_branch \
  --seed 0 \
  --n-retries 5 \
  --n-branch-continuations 2 \
  --manifest-path docs/experiments/main-benchmark/manifests/smoke/regex-log.json \
  --analysis-dir docs/experiments/main-benchmark/analysis/smoke/regex-log \
  --execute
```

The command writes the fixed-budget manifest, runs clean baselines and branch
roots, selects archive snapshots for `random_branch` and `promising_branch`,
runs continuations, writes `execution-report.json`, and builds analysis tables.
It skips jobs that already have `result.json` unless `--rerun-existing` is set.
Omit `--execute` to print the planned Harbor commands without spending credits.

Budget fields in these manifests and analysis tables are planning labels only.
They split a target token budget across methods for analysis, but Harbor and
the agent are not stopped when a job reaches the planned value. Treat
`budget_enforcement=planning_only` as a warning against strict fixed-budget
claims unless actual `total_tokens` are comparable.

The lower-level manual flow is still useful for debugging individual stages:

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name regex-log \
  --n-tasks 1 \
  --job-name phase4-smoke-regex-log-promising-branch-seed-0-root \
  --export-traces
```

After the root writes `archive.json`, launch promising continuations:

```bash
uv run python -m go_explore.cli continue-from-snapshots \
  jobs/phase4-smoke-regex-log-promising-branch-seed-0-root \
  --from-archive \
  --selector-mode archive_priority \
  --max-snapshots 2 \
  --job-prefix phase4-smoke-regex-log-promising-branch-seed-0 \
  --execute
```

For the random branch condition, run the random root, then use seeded random
archive selection:

```bash
uv run python -m go_explore.cli continue-from-snapshots \
  jobs/phase4-smoke-regex-log-random-branch-seed-0-root \
  --from-archive \
  --selector-mode random \
  --selector-seed 0 \
  --max-snapshots 2 \
  --job-prefix phase4-smoke-regex-log-random-branch-seed-0 \
  --execute
```

Build analysis tables after the observed jobs finish:

```bash
uv run python -m go_explore.cli build-analysis-tables \
  --manifest docs/experiments/main-benchmark/manifests/smoke/regex-log.json \
  --job-dir jobs/phase4-smoke-regex-log-single-seed-0 \
  --job-dir jobs/phase4-smoke-regex-log-promising-branch-seed-0-root \
  --continuation-report jobs/phase4-smoke-regex-log-promising-branch-seed-0-root/continuation-report.json \
  --event-log jobs/phase4-smoke-regex-log-promising-branch-seed-0-root/events.jsonl \
  --output-dir docs/experiments/main-benchmark/analysis/smoke/regex-log
```

Build figure source tables from completed analysis outputs:

```bash
uv run python -m go_explore.cli build-figure-tables \
  --task-summary docs/experiments/main-benchmark/analysis/smoke/regex-log/task-summary.csv \
  --run-summary docs/experiments/main-benchmark/analysis/smoke/regex-log/run-summary.csv \
  --execution-status docs/experiments/main-benchmark/execution-status.csv \
  --output-dir docs/experiments/figures
```

The manifest planner marks branch continuations as `pending_root_archive` until
the branch root creates snapshots. That is expected.

## Summaries

Summarize a job:

```bash
python -m go_explore.cli summarize-job jobs/oracle-smoke
```

List locally cached Harbor tasks:

```bash
python -m go_explore.cli list-cached-tasks
```

## Outputs To Inspect

| Path | Meaning |
| --- | --- |
| `jobs/<job>/config.json` | Harbor config used for the job. |
| `jobs/<job>/result.json` | Job-level trial counts, errors, and aggregate score. |
| `jobs/<job>/<trial>/result.json` | Trial reward, task name, and exception info. |
| `jobs/<job>/<trial>/trial.log` | Trial runtime log when present. |
| `jobs/<job>/<trial>/agent/trajectory.json` | Agent trajectory when traces are exported. |
| `jobs/<root>/continuation-report.json` | Continuation lineage and branch outcomes. |

## Common Failures

| Symptom | Likely Cause |
| --- | --- |
| `Cannot connect to the Docker daemon` | Docker is not running. |
| Daytona auth or sandbox creation error | `.env` is missing or has bad Daytona credentials. |
| Model/provider auth error | Model API key is missing or invalid. |
| `No module named 'go_explore'` | Export `PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"` before running global `harbor` with a custom agent import path. |
| No `trajectory.json` for oracle | Oracle runs may not export ATIF traces; inspect `result.json` instead. |
| No Daytona snapshots from Terminus run | Check that the command uses `--agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2`, not `--agent terminus-2`. |
