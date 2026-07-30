# T002 Experiment 1: Stable-Anchor Restore Validation — Pre-registration

Pre-registered 2026-07-30, before any Experiment 1 job (beyond the fix-git
canary) is launched. Fixed per `tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md`.

## Claim under test

On known stable Terminal-Bench tasks, a Go-Explore continuation restores a
real parent snapshot and solves the task within the same enforced aggregate
budget as the matched clean baseline. This validates restore reliability and
allows an efficiency comparison. It does **not** claim a solve-rate
advantage — these tasks have little/no solve-rate headroom.

## Fixed settings

- Dataset: `terminal-bench@2.0`
- Environment: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`
- Model: `anthropic/claude-haiku-4-5-20251001`
- Task timeout: harbor/Terminus-2 default (1200s agent-execution timeout,
  unchanged from prior batches — see `AgentTimeoutError` precedent in
  `docs/terminal-bench-task-log.md`)
- Aggregate token budget `B` = **500,000** (hard_token_limit, enforced via
  T001), revised 2026-07-30 after a first attempt at B=150,000 showed a high
  budget-exhaustion rate for `kv-store-grpc` and `log-summary-date-ranges`:
  solved jobs used up to 72,279 tokens, and budget-exhausted jobs had
  already consumed 45,000-74,217 tokens (median 64,302) before being cut off
  with more work left to do. B=500,000 gives per-job shares (100,000+ under
  the 30/35/35 split, well above the observed worst case) unlikely to bind
  on task difficulty alone. All four anchors were wiped and re-run fresh at
  this budget for a uniform comparison — no anchor mixes budgets.
- Root/child split: 30% root, two equal children (35% / 35%)
- Branch method: `promising_branch`, selector `archive_priority`,
  `context_mode=none` (primary condition per shared protocol — restored
  sandbox state, no parent reasoning)
- Clean baseline: `retry` method, `n_retries=3` — same number of independent
  job slots as the branch arm (1 root + 2 children = 3)
- Repetitions: 3 independent repetitions per anchor, labeled `seed=0,1,2`.
  These are **independent repetitions**, not proof of deterministic model
  sampling — the stack does not expose a model sampling seed.
- Children run regardless of root outcome (existing branch runner behavior:
  continuations execute once the root's archive is available, independent
  of root reward).

## Pre-registered anchors

- `kv-store-grpc`
- `pypi-server`
- `nginx-request-logging`
- `log-summary-date-ranges`

`fix-git` is run once as a harness canary only (validates hard-budget
metadata, archive/events, restore evidence, continuation lineage, and
analysis-table joins before the live batch) and is excluded from all
aggregate rates — every observed arm solves it.

## Primary outcomes to report

- restore validity rate: fraction of planned continuations with verified
  snapshot lineage (recorded parent snapshot + Daytona restore evidence)
- branch-arm solve rate vs. clean-baseline solve rate
- total enforced tokens, wall-clock time, snapshot overhead, restore overhead
- repeated setup/discovery work in clean retries vs. restored children

## Exclusion rules

A run is invalid for the primary result if it has a missing archive, missing
continuation lineage, incomplete token accounting, or a non-enforced
(`planning_only`) budget label. Invalid runs are still reported, not hidden.

## Operational constraint (added 2026-07-30, after an interrupted first attempt)

Daytona enforces a 100-snapshot-per-account cap. Running Experiment 1's 4
anchors and Experiment 2's 14-candidate screen concurrently (18 parallel
job lanes) exceeded it and caused a real snapshot-creation timeout mid-run.
Fix: experiments run one at a time — Experiment 1 to completion and analysis
before Experiment 2 is launched — and no more than ~5 concurrent job lanes
at once within an experiment. Two seed-1 branch roots (`kv-store-grpc`,
`nginx-request-logging`) completed without producing an archive because of
the interruption; their job directories were cleared and re-run rather than
recorded as invalid, since the failure was infra-induced, not a task-outcome.

## Job naming

`t002-exp1-<anchor>-{retry,promising-branch}-seed-{0,1,2}-...`, jobs dir
`jobs/`, manifests under
`docs/experiments/main-benchmark/manifests/t002-exp1-<anchor>.json`, analysis
under `docs/experiments/main-benchmark/analysis/t002-exp1-<anchor>/`.
