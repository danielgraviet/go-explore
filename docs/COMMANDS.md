# Commands

Short operator reference for running Go-Explore experiments in this repo.

## Setup

```bash
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"
```

Use the checked-in virtualenv when possible:

```bash
.venv/bin/python -m pytest -q
```

## tmux

Use the existing session when one is already running:

```bash
tmux list-sessions
tmux list-windows -t GoExplore-0 -F '#{window_index} #{window_name} #{window_active} #{pane_current_command}'
tmux capture-pane -t GoExplore-0:<window-name> -p -S -80
```

Launch a new window in that session:

```bash
tmux new-window -t GoExplore-0 -n <window-name> -c /Users/danielgraviet/Desktop/projects/go-explore
tmux send-keys -t GoExplore-0:<window-name> '<command>' Enter
```

## Run Experiments

Preferred entry point for fixed-budget benchmark runs:

```bash
.venv/bin/python -m go_explore.cli run-experiment \
  --dataset terminal-bench@2.0 \
  --task-name <task-name> \
  --experiment-id <experiment-id> \
  --job-prefix <job-prefix> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --total-token-budget 100000 \
  --method single \
  --method retry \
  --method random_branch \
  --method promising_branch \
  --seed 0 \
  --n-retries 5 \
  --n-branch-continuations 2 \
  --branch-context-mode preflight_verification \
  --manifest-path docs/experiments/main-benchmark/manifests/primary/<task-name>.json \
  --analysis-dir docs/experiments/main-benchmark/analysis/<experiment-id> \
  --execute
```

Use `--branch-context-mode none` for viability work when the point is to test
the restored sandbox without extra parent narrative.

For smoke runs, point at `docs/experiments/main-benchmark/manifests/smoke/<task>.json`
and `docs/experiments/main-benchmark/analysis/smoke/<task>/`.

## Continuations

If a root has already finished, run continuations from its archive:

```bash
.venv/bin/python -m go_explore.cli continue-from-snapshots \
  jobs/<root-job-dir> \
  --from-archive \
  --selector-mode archive_priority \
  --max-snapshots 2 \
  --job-prefix <continuation-prefix> \
  --execute
```

Use `--selector-mode random` with `--selector-seed 0` for the random-branch
control.

## Inspect Results

Summarize a completed Harbor job:

```bash
.venv/bin/python -m go_explore.cli summarize-job jobs/<job-name>
```

Inspect the main artifacts after a run:

```bash
python3 -m json.tool jobs/<job-name>/archive.json
tail -20 jobs/<job-name>/events.jsonl
```

Build analysis tables:

```bash
.venv/bin/python -m go_explore.cli build-analysis-tables \
  --manifest <manifest-path> \
  --job-dir jobs/<job-dir-1> \
  --job-dir jobs/<job-dir-2> \
  --continuation-report jobs/<root-job-dir>/continuation-report.json \
  --event-log jobs/<root-job-dir>/events.jsonl \
  --output-dir <analysis-dir>
```

## Current Benchmark Targets

- Claim 2: promising snapshot branching vs retry and random branch.
- Claim 1: `clean` vs `diff_only` vs `full_snapshot`.

Useful files:

- `docs/runbook.md`
- `docs/experiments/main-benchmark.md`
- `docs/experiments/viability-task-set.md`
- `docs/handoff-2026-07-27-preflight-verification-and-primary-set.md`

## Guardrails

- Do not change shared defaults just to run one experiment.
- Keep `planning_only` token budgets as labels, not hard caps.
- Record missing root archives and skipped continuations explicitly.
- Treat interrupted Harbor jobs as interrupted, not complete.
