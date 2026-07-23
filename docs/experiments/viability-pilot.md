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
tmux new-session -d -s phase6-viability-pilot '.venv/bin/python -m go_explore.cli run-viability-pilot --plan docs/experiments/viability/phase6-viability-pilot/viability-plan.json --analysis-dir docs/experiments/viability/phase6-viability-pilot/analysis --memo-path docs/experiments/viability-pilot.md --tmux-session phase6-viability-pilot --execute'
```

Attach command:

```bash
tmux attach -t phase6-viability-pilot
```

## Pilot Coverage

- Manifest arms: 9
- Observed job directories: 0
- Continuation reports: 0
- Event logs: 0
- Analysis run rows: 33
- Analysis task rows: 9
- Analysis warnings: 133

## Infrastructure Failures

- --agent-import-path is deprecated; use --agent instead. Daytona requires either DAYTONA_API_KEY, or both DAYTONA_JWT_TOKEN and DAYTONA_ORGANIZATION_ID, to be set. Please set the required environment variables and try again.
- branch continuations need a completed root job

## Decision

Do not launch the full batch unchanged; resolve infrastructure failures or missing planned rows first.
