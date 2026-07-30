# T007: Automatically Prune Completed Daytona Snapshots Above a Global Limit

## Goal

Automatically run safe global cleanup of completed Go-Explore Daytona snapshots
when the total remote `go-explore-*` snapshot count reaches a configurable
threshold (initially 50). Preserve the existing per-job retention limit; this
ticket cleans up the small retained set left behind after many completed jobs.

## Context

`GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT` already prunes snapshots live within one
running job/archive. It intentionally retains the best few remote snapshots so
the branch runner can restore from them. Those retained snapshots remain after
the root and children finish, so they accumulate across experiments.

`prune_snapshots.py` performs conservative manual cleanup today. It should be
refactored into reusable code and invoked automatically only after a job or
continuation batch has reached a safe terminal point. Do **not** run global
cleanup from the live snapshot-creation hook: a root may still need its
snapshots to select and launch continuations.

The current script has two issues to address before automation:

- it requests only one Daytona page (`limit=200`), so it can miss snapshots;
- its root safety check accepts any matching child directory despite its
  documentation requiring all downstream children to have launched.

Relevant files:

- `prune_snapshots.py`
- `go_explore/experiment_runner.py`
- `go_explore/continuations.py`
- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/manager.py`
- `tasks/phase-1/T005-daytona-snapshot-cleanup-runbook.md`

## Scope

1. Extract the safe snapshot discovery, ownership lookup, eligibility decision,
   and deletion logic from `prune_snapshots.py` into a typed reusable module.
   Keep the script as a thin CLI wrapper.
2. Implement global threshold semantics:
   - count only remote snapshot names prefixed `go-explore-`;
   - list all Daytona result pages, not only the first page;
   - do nothing when the global Go-Explore count is below the configured
     threshold;
   - when it reaches/exceeds the threshold, delete only snapshots that pass
     the safety policy;
   - report count before/after, eligible/deleted/failed/kept counts, and the
     reason for every kept or deleted snapshot.
3. Define a conservative root safety policy using explicit lineage artifacts:
   - never delete a snapshot owned by a job without `result.json`;
   - never delete a root snapshot until its continuation phase has reached a
     terminal recorded state (for example, a continuation report or an
     explicit no-continuation terminal record);
   - when continuations exist, require every planned child to have launched or
     reached a recorded terminal status before root snapshots become eligible;
   - do not infer this from a partial/`any child exists` filename match;
   - retain snapshots with missing/corrupt local lineage data.
4. Invoke threshold cleanup after safe terminal points in the managed
   experiment runner:
   - after a standalone/retry job completes;
   - after a root's continuation batch completes or is terminally skipped;
   - never between root completion and continuation planning.
5. Make automatic deletion opt-in through an explicit CLI/configuration value,
   such as `--auto-prune-snapshot-threshold 50`. The default remains disabled.
   Record the setting and cleanup result in the execution report.
6. Add an operational `--watch` mode to `prune_snapshots.py` for direct
   `harbor run` invocations that bypass `go-explore run-experiment`. It should
   poll at a configurable interval, prune only once the threshold is reached,
   and support a dry-run preview. Document that this is the coverage path for
   unmanaged jobs.
7. Update the cleanup runbook with the threshold behavior, managed-runner
   coverage, watch-mode use, safety conditions, and recovery guidance.

## Out of Scope

- Changing live per-job archive retention or snapshot scoring.
- Deleting non-`go-explore-*` Daytona snapshots.
- Deleting local `jobs/`, archives, trajectories, reports, or results.
- Automatically pruning an active root merely because the global threshold is
  exceeded.
- Background daemon installation, launch agents, cron configuration, or any
  user-machine persistence. `--watch` is process-scoped and user-started.
- Removing snapshots below the threshold unless the user explicitly runs the
  manual cleanup command without a threshold gate.

## Implementation Guidance

- Separate read-only planning from deletion. Implement an API that returns a
  deterministic cleanup plan before one that executes it; have dry-run and
  tests use the plan directly.
- Make `threshold` mean “start a cleanup pass at or above this count,” not
  “delete until exactly this count.” Safe snapshots may be fewer than the
  excess, and a conservative cleaner must leave the rest intact.
- Use Daytona pagination/cursors supported by the installed SDK. Fail closed:
  if listing is incomplete or pagination fails, do not delete snapshots based
  on a partial global count.
- Match snapshot names strictly and resolve ownership through local artifacts.
  Unknown names, active jobs, missing `result.json`, missing continuation
  evidence, and malformed reports must all be retained with a reason.
- Prefer continuation-report lineage/plan data over directory-name heuristics.
  If legacy reports lack enough data, retain their root snapshots rather than
  guessing; document the compatibility behavior.
- Make the managed-runner cleanup best-effort and non-fatal. A Daytona listing
  or deletion failure must be reported but must not change an already-complete
  task or continuation outcome.
- Avoid concurrent cleanup races: use a local process lock for managed cleanup
  and watch mode, re-check eligibility immediately before deletion, and treat
  “already deleted/not found” as an idempotent outcome.
- Emit structured execution-report data, not only console output, so cleanup
  actions can be audited after a benchmark batch.

## Suggested Starting Points

- Read the current `is_safe_to_delete`, `_job_dir_for_trial`, and
  `_children_exist` helpers in `prune_snapshots.py`.
- Trace terminal points in `run_fixed_budget_manifest` and
  `_run_branch_continuations` in `go_explore/experiment_runner.py`.
- Inspect `ContinuationReport` and continuation plans in
  `go_explore/continuations.py` for authoritative child lineage.
- Review Daytona list/delete abstractions in `go_explore/snapshots/backends.py`
  and existing archive retention tests in `tests/test_archive.py`.

## Acceptance Criteria

- The manual script retains its existing no-argument cleanup behavior and adds
  explicit threshold and watch options with dry-run support.
- A threshold-triggered pass counts every paginated `go-explore-*` snapshot
  and performs no deletion below the threshold.
- Above the threshold, only snapshots with completed and fully consumed root
  lineage, or completed non-root lineage, are eligible for deletion.
- An active root, a completed root with unlaunched/pending children, and a root
  with missing/corrupt continuation data are retained with explicit reasons.
- Root eligibility is determined from all planned continuation records, not
  from the existence of one child directory.
- Managed experiments run a best-effort threshold check only at safe terminal
  points and record the check/result in `execution-report.json`.
- Direct Harbor users can run `prune_snapshots.py --watch --threshold 50`
  without changing task behavior; the process never touches non-Go-Explore
  snapshots or local job artifacts.
- Pagination/listing failure, lock contention, and individual delete failure
  are visible and non-fatal; no unsafe deletion follows partial discovery.
- `uv run pytest -q` passes.

## Test Coverage

- Unit-test cleanup planning below, at, and above the threshold.
- Unit-test multi-page snapshot listing and a pagination failure; assert no
  deletion follows an incomplete list.
- Unit-test ownership and safety decisions for active jobs, completed retries,
  completed roots with no continuation terminal record, roots with pending
  children, and roots with every planned child terminal.
- Regression-test that one child directory alone does not make a root eligible.
- Test malformed/legacy archive and continuation-report artifacts fail closed.
- Test deletion execution: successful deletion, already-missing snapshot,
  failure, idempotent second pass, and only Go-Explore prefix selection.
- Test managed experiment-runner timing: no check between root and child
  planning; one check after terminal child batch; cleanup failure does not
  change task outcome.
- Test `--dry-run`, `--threshold`, and `--watch` argument behavior with a fake
  clock/client; do not call live Daytona in the default test suite.

## Validation

Run:

```bash
uv run pytest \
  tests/test_archive.py \
  tests/test_continuations.py \
  tests/test_experiment_runner.py -q
uv run pytest -q
```

Before enabling deletion, run:

```bash
uv run python3 prune_snapshots.py --threshold 50 --dry-run
```

Verify that every planned deletion has a completed root/child lineage and every
retained active or pending root has the expected reason. Enable the managed
threshold only after this preview is correct.

## Notes / Open Questions

- The exact pagination API depends on the installed Daytona SDK. Keep that
  SDK-specific code isolated behind a small client adapter.
- A threshold of 50 is an operational trigger, not a retention guarantee.
  If more than 50 snapshots are active or safely unprunable, the cleaner must
  report that condition and leave them intact.
