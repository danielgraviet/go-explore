# Experiment F results

Executed 2026-09-11. Protocol:
[env-progress-search.md](env-progress-search.md).
Do not fold these rows into Experiment 2 Phase B (17/25 vs 6/25) or
into Experiment E (S21 representation ablation).

Model: `anthropic/claude-haiku-4-5-20251001`. Aggregate budget B=600,000
(`hard_token_limit`). `n_retries=3`, `n_branch_continuations=2`,
`branch_root_fraction=0.3`, `branch_context_mode=none`,
`skip-if-root-solved`. Agent:
`go_explore.agents.factory:SnapshotAwareTerminus2`.

Both methods started from the planted warehouse snapshot
`go-explore-staged-service-repair__plant-step-0` (Experiment E plant,
reused; not replanted). Inclusion: every retry attempt and the branch
root Harbor command carried that `snapshot_template_name`. No job used
`--agent terminus-2` together with the import path. Restore overhead on
the four executed jobs was ~2.0–2.4s.

Harbor atexit `CancelledError` appeared after jobs, as in Experiment E;
it is noise, not a scored failure.

## Ceiling stop

The 1-seed practice race was **dual-ceiling**: retry solved and
promising_branch solved. Children were not launched (`skipped_root_solved`).
Seeds 1–4 were **not run**. That is the pre-registered stop, not an
infra abort.

This still helps Daytona: the useful product on this task is the saved
machine as a start template. It does **not** show that branching is a
better strategy than retry once that template is given to both sides.

## Primary table

`rescued` = root failed and a launched child scored 1.0.

| Seed | retry_solved | root_solved | children_launched | child_solved | rescued | branch_solved |
| --- | --- | --- | --- | --- | --- | --- |
| 0 (canary) | **yes** | **yes** | no (skipped) | — | no | **yes** |
| 1–4 | not run | not run | not run | — | — | not run |

Paired canary: retry **1/1**, branch **1/1**. Scored n=5 not collected.

Retry attempt detail on seed 0:

| Attempt | reward | exception | tokens |
| --- | ---: | --- | ---: |
| 0 | — | `AgentBudgetExhaustedError` | 210339 (overshoot of 200k cap) |
| 1 | **1.0** | | 83166 |
| 2 | **1.0** | | 61579 |

Branch root: reward **1.0**, 22615 tokens, children skipped.

The first retry burning the cap is a reminder that the plant is not an
automatic solve. Two of three retries still finished from that same
start, and so did the branch root, which is why the stop rule fired.

## What this supports

On staged-service-repair, once **both** methods restore the planted
warehouse snapshot, a single matched-budget practice race does not
separate retry from snapshot search. Daytona's demonstrated win on this
task remains Experiment E: the snapshot carries the sticky-note database
that a git patch does not (S21). Experiment F does not add a search
advantage, and it does not revise 17/25.

Sources:
`docs/experiments/main-benchmark/analysis/env-search-seed-0/`
and `jobs/env-search-*-seed-0-*`.
