# Phase 6 Viability Pilot

## Status

Executed pilot run.

## Artifacts

- Plan: `docs/experiments/viability/phase6-viability-pilot/viability-plan.json`
- Combined analysis manifest: `docs/experiments/viability/phase6-viability-pilot/analysis/pilot-combined-manifest.json`
- Execution report: `docs/experiments/viability/phase6-viability-pilot/analysis/execution-report.json`
- Run summary: `docs/experiments/viability/phase6-viability-pilot/analysis/run-summary.csv`
- Task summary: `docs/experiments/viability/phase6-viability-pilot/analysis/task-summary.csv`
- Warnings: `docs/experiments/viability/phase6-viability-pilot/analysis/warnings.json`

## Tmux

Launch command for this report:

```bash
tmux new-session -d -s phase6-build-cython 'set -a; source .env; set +a; export PATH="$HOME/.local/bin:$PATH"; export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"; .venv/bin/python -m go_explore.cli run-viability-pilot --plan docs/experiments/viability/phase6-viability-pilot/viability-plan.json --analysis-dir docs/experiments/viability/phase6-viability-pilot/analysis --memo-path docs/experiments/viability-pilot.md --tmux-session phase6-build-cython --execute'
```

Attach command:

```bash
tmux attach -t phase6-build-cython
```

## Pilot Coverage

- Manifest arms: 9
- Observed job directories: 33
- Continuation reports: 6
- Event logs: 21
- Analysis run rows: 33
- Analysis task rows: 9
- Analysis warnings: 34

## Decision

Pilot artifacts are complete enough to inspect solve rate, cost, tokens, snapshot overhead, and restore overhead before choosing full-batch arms.
