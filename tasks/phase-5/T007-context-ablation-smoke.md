# T007: Context Ablation Smoke Run

## Goal

Run a small paid smoke experiment that directly tests whether parent context helps or hurts snapshot continuation.

## Context

After implementing explicit context modes, we need one narrow experiment before returning to larger benchmark execution. The target question is whether branch failures improve when using `full_snapshot + none` or `full_snapshot + critical_parent_summary`.

Depends on:

- P5-T002: Explicit Context Mode Controls
- P5-T003: Critical Parent Summary Mode
- P5-T006: Budget Enforcement Or Explicit Labels

## Scope

Create and run a smoke manifest for `regex-log` comparing:

- scratch retry,
- `full_snapshot + parent_summary`,
- `full_snapshot + none`,
- `full_snapshot + critical_parent_summary`.

Use a small seed count and low-cost model settings consistent with the current runbook. Write a result memo with exact commands, job paths, costs, solve rates, and interpretation.

## Out of Scope

- Do not run the full paper benchmark.
- Do not include many tasks.
- Do not tune prompts after seeing the first result inside this ticket.

## Suggested Starting Points

- `go_explore/cli.py`
- `go_explore/experiment_runner.py`
- `docs/runbook.md`
- `docs/experiments/regex-log-r3-audit.md`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/`

## Acceptance Criteria

- The smoke run produces result artifacts under a new unique job prefix.
- The run includes at least one continuation for each tested context mode.
- The memo reports solve rate, cost, token accounting, and snapshot/restore overhead where available.
- The memo states whether the result supports or weakens the inherited-context hypothesis.

## Validation

Run the planned command in a tmux session and record it in the memo.

After completion, run or inspect:

```bash
uv run python -m go_explore.cli build-analysis-tables --help
test -f docs/experiments/<new-smoke-memo>.md
```

Replace `<new-smoke-memo>` with the actual memo path used in the PR.

## Notes / Open Questions

This ticket intentionally spends Daytona/model credits. Keep the run small and stop if infrastructure fails before any valid comparison is produced.
