# Experiment A: Representation Ablation — Pre-registration

Pre-registered 2026-08-15, before any Claim 1 live job is launched.
Do not interpret Aug 6 checkpoint-diagnostic canaries as this experiment.
Those jobs ran while Daytona snapshotting was broken
([tasks/aug-6-fixes/context.md](../../tasks/aug-6-fixes/context.md)).

This experiment is **diagnostic-only**. Do not fold its rows into the
Experiment 2 Phase B headline table (17/25 vs 6/25).

## Claim under test (ledger P1)

Given the same parent checkpoint and the same remaining token cap, is a
full Daytona snapshot a better child start state than compressed
alternatives?

Possible outcomes, all publishable:

- snapshot >> compressed: environment state is the missing reusable unit.
- snapshot ≈ compressed: full snapshots are not worth the infra cost.
- snapshot < compressed: inherited environment state can be harmful.

## Arms

Same parent snapshot, same `remaining_token_budget`, Haiku 4.5:

| Arm | `start_state_type` | `context_mode` |
| --- | --- | --- |
| clean | `clean` | `original_task_only` |
| diff_only | `diff_only` | `original_task_only` |
| diff_transcript | `diff_only` | `full_transcript_summary` |
| command_replay | `command_replay` | `original_task_only` |
| full_snapshot | `full_snapshot` | `none` |

`full_snapshot` uses `none` so the arm isolates environment restore from
parent narration. Context effects were already measured on regex-log
([docs/experiments/context-ablation-smoke-20260722.md](context-ablation-smoke-20260722.md)).

## Fixed settings

- Dataset: `terminal-bench@2.0`, env: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`
- Model: `anthropic/claude-haiku-4-5-20251001`
- Remaining cap R: **200,000** tokens (`hard_token_limit`) on every child arm
- Root is observation-only (same caveat as checkpoint-diagnostic v1: the
  live root cannot be paused at an exact cap while keeping in-memory context)
- Tasks: `extract-elf`, `regex-log` (the two tasks with documented restore
  signal). Optional third: `custom-memory-heap-crash` if snapshotting is
  healthy and budget remains.
- Seeds: 5 independent roots per task. One checkpoint per root (highest
  `archive_priority` cell that is not a bare completion claim).
- `parent.diff` must exist on the root job before execute. If missing, the
  diff arms stay `pending_parent_diff` and the seed is invalid for Claim 1.

## Primary outcomes

For each seed, a 5-way table: reward, tokens, wall clock, restore overhead,
exception. Lead with paired per-seed solve, not a pooled percentage.

Inspect `representation-ablation.json` before treating a seed as evidence:

- `diagnostic_only` is `true`
- every arm has the same `planned_token_cap`
- `full_snapshot` names the selected snapshot and `start_state_type: full_snapshot`
- clean / diff / replay arms have `start_state_type` matching the table above

## Exclusion rules

Invalid for the primary result: missing archive, snapshot not in archive,
`pending_parent_diff` at execute time, `planning_only` budget label, Harbor
built-in agent used instead of the snapshot wrapper, restore
`DaytonaValidationError`. Report invalid seeds; do not hide them.

## Execution

Dry-run first (no Harbor):

```bash
uv run python -m go_explore.cli representation-ablation \
  jobs/<root-job> \
  --snapshot-name <exact-daytona-snapshot-name> \
  --remaining-token-budget 200000 \
  --job-prefix <root-job>-claim1 \
  --diff-path jobs/<root-job>/parent.diff
```

Execute only after Daytona snapshot listing returns the named snapshot
and a `checkpoint-diagnostic` dry-run on the same snapshot succeeds.

Concurrency: one seed at a time. Daytona account snapshot cap is ~100.

## Result memo location

Write each completed seed to
`docs/experiments/main-benchmark/analysis/claim1-<task>-seed-<n>/`
and a rollup at `docs/experiments/claim1-representation-ablation-results.md`.
Until that file exists, Claim 1 is **not supported**.
