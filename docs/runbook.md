# Runbook

Use this page to verify the project before and after changes.

## Prereqs

- Python env managed by `uv`.
- Harbor installed and available as `harbor`: need version 0.19.0 with the `daytona` extra.
- Docker running for local Docker Harbor runs.
- `.env` with Daytona/model credentials for Daytona or model-backed runs.

E2E tests and live Harbor runs may call Harbor, Docker, Daytona, and model APIs. Do not treat them as required for every code change.

## Cheap Checks

Run normal tests:

```bash
uv run pytest -v
```

Run a focused file while developing:

```bash
uv run pytest tests/test_harbor.py -q
```

## E2E Checks

Run e2e tests explicitly:

```bash
uv run pytest -v -k e2e
```

Or:

```bash
uv run pytest --run-e2e -s
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
  --agent go_explore.agents.factory:SnapshotAwareTerminus2
```

Do not pass `--agent terminus-2` with this command. Harbor will use the built-in agent and skip the import-path wrapper.

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
| No Daytona snapshots from Terminus run | Check that the command uses `--agent go_explore.agents.factory:SnapshotAwareTerminus2`, not `--agent terminus-2`. |
