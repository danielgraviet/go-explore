# T004 — Small comparative pilot (post-fix)

## Goal
Measure whether the T001 fix actually moves the two headline metrics:
solve-rate lift from branching, and token efficiency, on tasks that are
actually diagnostic (not `fix-git`, which is saturated — see phase-6
failure analysis).

## Tasks
- `regex-log` (known partial-progress dynamics, already instrumented)
- `sqlite`-related task (user-reported mixed results — better signal than
  a task that always passes or always fails)

Do not include `fix-git` as an evidence task; it may still run as a cheap
canary but its result doesn't count toward conclusions.

## Design
Per task, n=3-5 seeds, compare:
- `retry` (baseline)
- `promising_branch`, `context_mode=none`
- `promising_branch`, `context_mode=failure_symptom`

Use `plan-viability` / `run-viability-pilot` per `docs/runbook.md` rather
than hand-rolling manifests.

## Metrics to record
- Solve rate per arm per task.
- Total tokens per *successful* run (not just totals — a branch that fails
  cheaply is not "efficient," it's just cheap and wrong).
- For branch arms: is the selected/restored snapshot's step_id later than
  step 0 / than the root's first candidate (sanity check that T001 is
  actually engaging, using the same inspection as T003).

## Pass condition
Not a hard pass/fail gate — this is a measurement task. Write findings
back into `docs/phase6-failure-analysis.md` or a new dated follow-up doc.
Decide from results whether T006 (context-mode redesign) is warranted, or
whether the archive fix alone was sufficient.

## Status
Done (n=3, not n=5 — see below). Ran `regex-log` and `sqlite-db-truncate`,
each with `retry` (n=3) + `promising_branch` at `context_mode=none` (root +
2 children) and `context_mode=failure_symptom` (root + 2 children).
Manifests/analysis under `docs/experiments/main-benchmark/{manifests,analysis}/t004/`.

Along the way, `--branch-context-mode failure_symptom` immediately raised
`ValueError: branch_context_mode must be 'parent_summary', ...` — the
`_validate_config` whitelist in `go_explore/fixed_budget.py:231` was never
updated when `failure_symptom` was added to `ContextMode`. Fixed (added it
to the allowed set); no Harbor jobs were spent on the failed validation
calls since it fails before planning. Full test suite still passes (197
passed, 9 skipped).

### Result: zero solves, all arms, both tasks (n=3)

| task | retry | branch(none) | branch(failure_symptom) |
|---|---|---|---|
| regex-log | 0/3 | 0/3 (root+2 fork, 1 child ran, 1 missing_result — only 1 archive cell existed) | 0/3 (same: 1 child ran) |
| sqlite-db-truncate | 0/3 | 0/3 (2 children, 2 cells) | 0/3 (2 children, 2 cells) |

No task solved under any condition, so the ticket's headline metrics
(solve-rate lift, tokens-per-success) are **not computable** from this
pilot — there are no successes to compare. This is a null result, not
evidence for or against the archive fix.

Secondary observations that are informative even without a solve:
- The `missing_result` rows for a couple of children aren't bugs — the
  archive only had 1-2 cells to fork from (small trajectories, few
  distinct candidates), so some of the 2 planned continuation slots per
  root had nothing to run against. Consistent with failure-analysis item 9.
- Checked `archive.json` for both roots: neither one happened to produce
  repeated edits to the same cell this run, so T001's tie-break fix wasn't
  actually exercised in this particular pilot (T002 and T003 already
  confirmed it works; this pilot just didn't generate the triggering
  condition). The `sqlite` root's best cell was a `test_run` with
  `tests_passed: null` (score 1.0, ambiguous signal, not a confirmed pass)
  — the archive had no strong "close to done" state to hand off either
  time.

### Interpretation
n=3 is too small to distinguish signal from noise on tasks this hard for
haiku (regex-log and sqlite-db-truncate both went 0/9 total attempts
combined per task across all arms). Root causes could be: (a) genuinely
too hard for haiku within this budget regardless of snapshot restoration,
(b) archive rarely capturing a state that's actually "close" (see the
ambiguous `test_run` note above — scoring still doesn't distinguish a
confirmed pass from a ran-but-unclear validation), or (c) just variance at
this sample size.

### Recommendation (not yet executed — needs a decision before spending more)
Do not scale straight to n=5 on the same two tasks yet. Options, in order
of cost:
1. Re-run replay-style analysis (like T002) across more archived
   trajectories already on disk to check the "no repeated edits" and
   "ambiguous test_run scoring" pattern before spending more credits.
2. Pick one task with a higher baseline solve rate for haiku (so branch
   children have a real chance to build on genuine progress) instead of
   two tasks both near 0% — trade diagnostic purity for actually
   measuring the mechanism.
3. If sticking with regex-log/sqlite, raise n substantially (10+) to get a
   usable solve-rate estimate, accepting the added cost.

## Follow-up: regex-log-only, n=8 (executed)

Per recommendation above, narrowed to `regex-log` only (established ~20%
baseline from earlier phase4 data) and raised n to 8: `retry` (8
attempts, 1 seed) vs `promising_branch(context_mode=none)` (8 seeds, 1
child per root). Manifests/analysis under
`docs/experiments/main-benchmark/{manifests,analysis}/t004b/`.

**Result: retry 0/8 solved. Branch: `solved=true`,
`unique_success_beyond_baselines=true`.**

Per-run breakdown (`analysis/t004b/branch/run-summary.csv`):
- seed-1: root fail (reward 0.0) → child restored from step-5 snapshot →
  **success (reward 1.0)**.
- seed-5: root `agent_error` → child restored from step-1 snapshot →
  **success (reward 1.0)**.
- seed-0, seed-2: inverse pattern — root succeeded, child (continuing from
  a mid-trajectory snapshot instead of stopping) then failed. Worth a
  separate look: continuing past an already-successful root can regress.
- seed-3, 4, 6, 7: fail on both root and child.

This is the first pilot data showing branching recover from root failure
at a rate retry didn't match (2/8 vs 0/8). Small n, so treat as a
promising signal, not a settled result — but it's the concrete instance
of the "root fails, child picks up and finishes" pattern this whole
effort has been chasing.

### Open follow-ups (not yet tickets)
- Investigate the seed-0/seed-2 regression pattern (child fails after a
  successful root) — could indicate continuing past a done task, or a bad
  snapshot choice mid-success, causes harm.
- Re-run with `failure_symptom` context mode at the same n to see if it
  changes the 2/8 recovery rate.
- Consider whether this specific result should be replicated (a second n=8
  batch) before treating 2/8 as a stable estimate.
