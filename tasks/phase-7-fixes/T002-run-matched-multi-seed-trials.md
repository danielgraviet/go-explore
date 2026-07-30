# T002: Run Matched Multi-Replication Terminal-Bench Trials

## Goal

Produce two clean, hard-token-budget experiment sets for Go-Explore on
Terminal-Bench:

1. a stable-anchor experiment showing that checkpoint/restore reliably
   preserves enough useful state to solve the same known-solvable tasks within
   one enforced aggregate budget; and
2. a screened headline benchmark testing whether selected snapshot branching
   solves more tasks than matched clean retries at that same budget.

Do not combine these claims. The first establishes operational reliability and
efficiency on stable tasks; the second is the evidence for a solve-rate gain.

## Context

The existing positive tasks repeatedly solve at the root, so they have little
or no solve-rate headroom. They are useful anchors for checking that a child
can restore real state and finish the task within the branch arm's aggregate
budget, but cannot support a claim that branching solves *more* tasks.

The headline result needs tasks that are neither ceiling-effect tasks nor
effectively impossible for the selected model (`claude-haiku-4-5-20251001`).
Task selection must therefore be based on a pre-registered, clean-retry
qualification screen—not on branch outcomes.

This task depends on T001. Do not launch either experiment until token limits
are genuinely enforced and the reports distinguish enforced runs from legacy
`planning_only` artifacts. Exclude snapshot-hook failures and incomplete
lineage from both analyses.

References:

- `docs/terminal-bench-task-log.md`
- `docs/experiments/viability-task-set.md`
- `docs/phase6-failure-analysis.md`
- `docs/experiments/main-benchmark.md`
- `tasks/phase-7-fixes/T001-enfore-token-budget.md`

## Shared Protocol

- Dataset/environment/model: `terminal-bench@2.0`, Daytona, and the current
  snapshot-aware Terminus-2/Haiku configuration. Record the exact versions,
  model identifier, task revision, and agent kwargs in the manifest.
- Unit of comparison: one task × independent repetition × method. If the
  stack cannot set a model sampling seed, call these **independent
  repetitions**, not seeded trials. The existing planner's `seed` is not proof
  of deterministic model sampling.
- Budget: use the hard aggregate token cap supplied by T001. Every compared
  arm gets the same total `B`; a branch root plus all of its child allocations
  sum to `B`.
- Primary branch condition: `promising_branch` with `context_mode=none`.
  The child receives restored sandbox state but no parent reasoning. Keep
  parent-summary modes out of primary results.
- Baseline: clean retries with the same aggregate budget and the same number
  of independent job slots as the branch arm. Report a single long clean run
  only as supplemental context, never as the primary comparator.
- Required artifacts: manifest, execution report, root archive/events,
  continuation report, per-job token accounting, snapshot/restore timing, and
  analysis tables. A run with a missing archive, missing lineage, incomplete
  token accounting, or non-enforced budget is invalid for the primary result.
- Pre-register task IDs, repetitions, budget `B`, root/child split, selector,
  context mode, task timeouts, and exclusion rules before launching branch
  jobs. Do not replace a task after seeing a branch outcome.

## Experiment 1: Stable-Anchor Restore Validation

### Claim

On known stable Terminal-Bench tasks, a Go-Explore continuation restores a
real parent snapshot and solves the task within the same enforced aggregate
budget as the matched clean baseline. This validates restore reliability and
allows an efficiency comparison; it does **not** claim a solve-rate advantage.

### Pre-registered Tasks

Use these four stable positive anchors:

- `kv-store-grpc`
- `pypi-server`
- `nginx-request-logging`
- `log-summary-date-ranges`

Use `fix-git` only as a one-repetition harness canary. Exclude it from all
aggregate rates because every observed arm solves it.

### Design

- Run 3 independent repetitions per anchor.
- For each repetition, run matched clean retries and one `promising_branch`
  arm under total cap `B`.
- Use the same root/child allocation for every branch repetition. The initial
  default may remain 30% root and two equal children, but commit the final
  split before execution.
- Execute planned children even if the root succeeds. This verifies that a
  restored child can operate from the saved state; report root and child
  outcomes separately.
- Require the continuation record to prove it used the intended snapshot (for
  example, the recorded parent snapshot and Daytona restore evidence).

### Primary Outcomes

- restore validity rate: fraction of planned continuations with verified
  snapshot lineage;
- branch-arm solve rate and clean-baseline solve rate;
- total enforced tokens, wall-clock time, snapshot overhead, restore overhead;
- repeated setup/discovery work in clean retries versus restored children.

### Interpretation

Success means all valid anchor continuations restore correctly and the branch
arm solves at least as reliably as its matched baseline within cap `B`.
Report any lower repeated setup or lower wall-clock time as efficiency evidence
only. Because the roots are likely ceiling-effect successes, do not describe a
tie or lower cost as “more tasks solved.”

## Experiment 2: Screened Headline Solve-Rate Benchmark

### Claim

On pre-registered Terminal-Bench tasks that are neither too easy nor too hard
for Haiku, selected snapshot branching solves more tasks than matched clean
retries under the same enforced aggregate token budget.

### Qualification Screen

Before any branch result is inspected, define a candidate pool of approximately
12–16 usable tasks. Include a mix of setup/build, debugging, service, and
artifact-heavy coding tasks. Existing candidates worth considering include
`build-cython-ext`, `git-leak-recovery`, `custom-memory-heap-crash`,
`code-from-image`, `pytorch-model-recovery`, and new tasks vetted from the
cached Terminal-Bench inventory.

For each candidate, run 3 independent **clean** repetitions at cap `B`.
Select up to 10 headline tasks using only these screen results and pre-recorded
metadata:

- retain tasks with 1–2 solves out of 3 clean repetitions (initial target:
  approximately 20–80% clean success);
- retain only tasks with a verified snapshot-capable root path or a documented
  reason the branch root is expected to produce candidate snapshots;
- retain a mix of task categories rather than selecting only the easiest
  survivors;
- exclude 0/3 tasks as too hard at cap `B`, 3/3 tasks as ceiling-effect tasks,
  tasks with missing archive/events or restore failures, and tasks whose
  timeout/infrastructure cost makes the cap non-comparable.

Publish the candidate pool, screen outcomes, exclusions, and final task list
before launching Experiment 2 branch arms. A task may be replaced only for a
documented pre-existing infrastructure failure, with a replacement from the
same category selected before its outcomes are viewed.

### Main Design

- Run 5 independent repetitions for each selected task and method.
- Primary methods:
  - matched clean retries;
  - `promising_branch`, using the pre-registered selector and
    `context_mode=none`.
- Give both methods aggregate cap `B`. The branch root and its children must
  exactly sum to `B`; clean retry slots must also sum to `B`.
- Add `random_branch` only if budget permits. It is the preferred secondary
  control for showing whether selection adds value beyond restoring arbitrary
  snapshots. Do not reduce the clean-vs-promising replication count to fund it.
- Keep the selector, root/child split, task timeout, and model fixed across
  all selected tasks. Treat `critical_parent_summary` as a separate diagnostic
  ablation, not a primary arm.

### Primary Analysis

Report at both levels:

- **repetition level:** whether any job in the arm solved, total observed
  tokens, time, and valid/invalid status;
- **task level:** solve rate across five repetitions for clean retry and
  promising branch, plus the paired difference in solved repetitions.

The headline statistic is the aggregate paired solve-rate difference across
the pre-registered selected task set. Include a confidence interval appropriate
for paired binary repetitions (for example, a paired bootstrap interval), the
per-task table, and the number of invalid/excluded repetitions. Do not pool
individual child jobs as independent task attempts.

Also report selected snapshot cell keys, restore verification, repeated-work
metrics, and final-state/path-diversity measures. These explain *why* a branch
won or lost but are secondary to the equal-budget solve-rate comparison.

### Stop and Failure Rules

- Stop and mark the affected task invalid if the hard budget, archive/events,
  restore lineage, or token accounting is missing.
- Do not stop merely because one method is losing.
- Pause the batch if a recurring snapshot-hook or provider/infrastructure
  failure affects more than one task; fix and re-qualify before continuing.
- Do not include `sqlite-db-truncate` or `sanitize-git-repo` in the headline
  set unless they pass the clean-screen criterion. They remain useful negative
  safety anchors even if excluded.

## Deliverables

- A versioned pre-registration manifest for Experiment 1 and the Experiment 2
  candidate screen, including all budgets and fixed settings.
- A screen report listing every candidate, clean outcomes, exclusion reason,
  and the final set of up to 10 headline tasks.
- Execution and analysis directories for both experiments with complete
  manifests, reports, event logs, continuation reports, tables, and warnings.
- A concise result memo that states the stable-anchor and headline claims
  separately, includes all invalid runs, and avoids causal claims from
  parent-summary or planning-only data.
- An update to `docs/terminal-bench-task-log.md` after each batch.

## Acceptance Criteria

- Both experiments use T001's hard token enforcement; no primary row is
  labeled `planning_only`.
- Experiment 1 has four anchors × three independent repetitions, complete
  restore lineage, and separate root/child/arm outcomes.
- Experiment 2 publishes its clean-only qualification screen and final task
  set before branch outcomes are launched or inspected.
- The final headline set contains no more than 10 tasks and excludes ceiling,
  impossible-at-cap, and infrastructure-confounded tasks according to the
  published rules.
- Experiment 2 runs five matched independent repetitions per selected task for
  clean retry and promising branch with equal aggregate cap `B`.
- The analysis reports paired task-level solve-rate results, actual aggregate
  token use, invalid rows, and per-task outcomes; it does not count children
  as independent task-level samples.

## Validation

- Dry-run every manifest and verify per-method allocations sum exactly to `B`.
- Before the live batch, run one `fix-git` canary through the full sequence and
  verify hard-budget metadata, archive/events, restore evidence, continuation
  lineage, and analysis-table joins.
- After each batch, run the repository analysis command(s) and inspect
  `run-summary.csv`, `task-summary.csv`, `warnings.json`, and each root's
  `continuation-report.json`.
- Run the focused regression suite after any harness/configuration change:

```bash
uv run pytest \
  tests/test_continuations.py \
  tests/test_experiment_runner.py \
  tests/test_analysis_tables.py \
  tests/test_cli.py -q
```

## Out of Scope

- Implementing hard token enforcement (T001).
- Changing selector behavior, cell definitions, or snapshot timing.
- Treating stable-anchor results as a solve-rate win.
- Post-hoc task selection based on branch success.
