# T001: Regex-Log R3 Result Audit

## Goal

Turn the `regex-log-r3` smoke run into a short, durable result memo that identifies what failed and what hypotheses the next implementation tickets should test.

## Context

The `regex-log-r3` run showed that scratch retry can solve the task, while `random_branch` and `promising_branch` continuations did not. Before changing policy, capture the exact evidence so later PRs can compare against it.

Depends on:

- Completed `phase4-smoke-regex-log-r3` run artifacts

## Scope

Write `docs/experiments/regex-log-r3-audit.md` covering:

- per-method solve rates,
- positive retry attempts,
- branch root and continuation outcomes,
- selected snapshot names and cell keys,
- observed snapshot overhead,
- evidence for inherited-state or parent-summary failure modes,
- limitations of this single-task smoke run.

## Out of Scope

- Do not change benchmark code.
- Do not rerun the experiment.
- Do not generalize beyond the observed smoke result.

## Suggested Starting Points

- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/run-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/task-summary.csv`
- `jobs/phase4-smoke-regex-log-r3-random-branch-seed-0-root/continuation-report.json`
- `jobs/phase4-smoke-regex-log-r3-promising-branch-seed-0-root/continuation-report.json`
- child `agent/trajectory.json` files under `jobs/phase4-smoke-regex-log-r3-*snapshot-*`

## Acceptance Criteria

- The memo names every completed job and its reward.
- The memo identifies retry attempts `0` and `3` as the only solved runs, if the source artifacts still show that.
- The memo separates infrastructure issues from research/policy failures.
- The memo states at least three concrete hypotheses for follow-up tickets.
- The memo links to the local artifacts used as evidence.

## Validation

Run:

```bash
test -f docs/experiments/regex-log-r3-audit.md
rg -n "retry|random_branch|promising_branch|AgentTimeoutError|parent_summary|snapshot_overhead" docs/experiments/regex-log-r3-audit.md
```

Also manually spot-check the memo against `run-summary.csv`.

## Notes / Open Questions

This is a research memo, not a proof. Keep conclusions appropriately narrow.
