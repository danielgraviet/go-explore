# Phase-6 Fixes: Results (T001-T005)

This documents the outcome of the phase-6 fix tickets in `tasks/phase-6-fixes/`,
following on from `docs/phase6-failure-analysis.md`. It records what was
changed, what was verified, and the first evidence of branching recovering
from a root failure.

## T001: Archive tie-break fix

`SnapshotArchive.add` (`go_explore/snapshots/archive.py`) only replaced a
cell's stored snapshot when a new candidate scored strictly higher than the
incumbent. Repeated edits to the same file(s) usually score identically
under the flat heuristic scorer, so ties went to the incumbent — the
archive froze on an agent's *first*, least-refined attempt at a file and
could never represent later, more-refined progress.

Verified against the real `regex-log` root job
(`jobs/phase6-viability-pilot-regex-log-promising-branch-none-...`):
`/app/regex.txt` was edited at steps 0, 3, 5, 7, all scoring 1.25. Only
step 0 was ever accepted.

Fix: changed the tie-break so a later candidate that ties the incumbent
replaces it (`incumbent.score > score` instead of `>=`). One line, plus a
regression test.

## T002: Offline replay verification

Replayed the real `regex-log` root trajectory
(`.../regex-log__agZndfb/agent/trajectory.json`) through the patched
policy + archive, outside of Harbor/Daytona. Confirmed: candidates for
`/app/regex.txt` occurred at steps 3, 6, 8, 10; the archive now retains
**step 10** (the latest) instead of freezing on step 3.

## T003: Live Daytona confirmation

Ran a live 1-seed root job (`jobs/t003-regex-log-root-smoke`). The
`<discovery>` cell had two tied candidates (steps 5 and 9, both scoring
1.0); the archive kept step 9. Confirms the fix works end-to-end through
the real snapshot-creation pipeline, not just in replay.

## T004: Comparative pilot

### First pass: regex-log + sqlite-db-truncate, n=3, two context modes

Zero solves across all four arms (`retry`, `promising_branch` at
`context_mode=none` and `context_mode=failure_symptom`) on both tasks.
Not enough data to say anything about solve-rate lift or token
efficiency — a null result, not a negative one.

Also found and fixed a stale validator: `go_explore/fixed_budget.py`
rejected `failure_symptom` as a `--branch-context-mode` value even though
it's a valid `ContextMode` — the whitelist was never updated when that
mode was added. Fixed; no jobs were wasted since it fails at planning
time before any Harbor job runs.

### Second pass: regex-log only, n=8

Narrowed to `regex-log` alone (it has an established ~20% baseline for
haiku from earlier phase4 data, unlike `sqlite-db-truncate` which has no
known baseline). Compared `retry` (8 independent attempts) against
`promising_branch` at `context_mode=none` (8 independent root+child
chains, 1 child per root).

**Result:**

| method | solved | n |
|---|---|---|
| retry | 0/8 | 8 |
| promising_branch | 2/8 chains produced a success | 8 |

Per-chain detail:

- **seed-1**: root failed (reward 0.0) → child restored from a step-5
  snapshot → **succeeded** (reward 1.0).
- **seed-5**: root errored (`agent_error`) → child restored from a step-1
  snapshot → **succeeded** (reward 1.0).
- **seed-0, seed-2**: inverse pattern — root already succeeded, but the
  child continued anyway (restoring a mid-trajectory snapshot instead of
  stopping) and then **failed**. Continuing past an already-solved root
  can regress the outcome, not just waste tokens.
- seed-3, 4, 6, 7: failed on both root and child.

This is the first pilot evidence of the target pattern: a root that fails
or errors, followed by a child that restores a snapshot and completes the
task, at a rate (2/8) that plain retry did not match (0/8) at the same n.
Small sample — treat as a promising signal to replicate, not a settled
result.

Open follow-ups, not yet tickets:
- Investigate the seed-0/seed-2 regression (successful root, failed
  child) as a distinct failure mode.
- Re-run at the same n with `context_mode=failure_symptom` to see if it
  changes the 2/8 recovery rate.
- Replicate the n=8 regex-log-only batch before treating 2/8 as stable.

## T005: build-cython-ext infra check

Re-ran the `build-cython-ext` root once. It completed cleanly this time
(`n_completed_trials: 1`, vs. stuck-pending before) and produced a healthy
archive (4 cells, including `test_run` candidates scoring 16.5-21.25).
Confirms the earlier `n_snapshots_created: 0` in the phase6 pilot was a
transient Harbor/Daytona infra failure, not a snapshot-policy gap. No code
change needed for this task shape.

## T006: still blocked

Context-mode redesign remains deferred. The regex-log n=8 result used
`context_mode=none` and still produced recoveries, so there isn't yet a
case that a narrative handoff is necessary — but the open follow-up to
compare against `failure_symptom` at the same n is the natural next test
before touching T006.
