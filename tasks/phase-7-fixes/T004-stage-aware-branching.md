# T004: Add Stage-Aware Snapshot Eligibility and Selection

## Goal

Make snapshot selection aware of a coding task's progress stage so branch
continuations start from meaningful, reusable checkpoints rather than arbitrary
or duplicate mid-trajectory states. The policy should recognize setup,
diagnosis, implementation, validation, and risky/final mutation stages, retain
at most one best candidate per useful stage, and select a safe progression of
states for the available child slots.

This ticket keeps the existing root-then-continuation execution model. It does
not interrupt a root agent early or launch children while the root is running.

## Context

The current runner creates snapshots during a root run and selects the top
`k` archive entries only after that root completes. The existing archive cell
is primarily based on changed files, so multiple snapshots can represent the
same unfinished edit while a valuable setup or reproducible-diagnosis state is
lost. This is particularly risky for tasks such as `regex-log`,
`sqlite-db-truncate`, `sanitize-git-repo`, and `large-scale-text-editing`,
where late unvalidated work can trap a child in the parent's wrong state.

T003 adds the structured state signals needed here: verified setup, real
validation, persistent progress, persisted discovery, and risk. This ticket
uses those signals to create a small deterministic stage policy; it must not
reimplement their command parsing or validation detection.

Relevant references:

- `tasks/phase-7-fixes/T003-improve-state-selection.md`
- `docs/terminal-bench-task-log.md`
- `docs/experiments/viability-task-set.md`
- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/selectors.py`
- `go_explore/experiment_runner.py`
- `go_explore/continuations.py`

## Scope

1. Define a compact, ordered stage taxonomy backed by T003 signals:
   - `setup`: verified reusable dependencies, build output, generated artifacts,
     or service readiness;
   - `diagnosis`: a reproducible task failure plus persistent diagnostic
     artifact or state the child can inspect;
   - `implementation`: safe, task-relevant persistent progress after setup or
     diagnosis;
   - `validation`: real verifier/test evidence showing partial or complete
     progress;
   - `risky_final`: a destructive, final-answer, or unvalidated bulk mutation.
2. Assign one primary stage and explicit reasons to each newly archived
   snapshot. Preserve T003's multi-label signals as the underlying facts.
3. Extend archive identity/retention so snapshots from different primary
   stages are not collapsed merely because they touch the same files. Within a
   stage, retain the best candidate deterministically.
4. Add a named stage-aware selector mode that:
   - excludes `risky_final` entries unless T003 supplies the documented
     positive-validation exception;
   - chooses at most one entry per primary stage;
   - prefers `validation`, then `implementation`, then `diagnosis`, then
     `setup` when scores are otherwise comparable;
   - fills remaining child slots with the best eligible unselected stage;
   - falls back to the existing selector behavior when stage metadata is
     absent, so old archives remain usable.
5. Record primary stage, stage reasons, and stage-aware selection reasons in
   archive JSON, snapshot/selection events, and continuation reports.
6. Make the stage-aware selector available through the existing CLI and fixed
   budget/experiment configuration without changing default behavior unless a
   separate decision explicitly promotes it.

## Out of Scope

- Stopping a root at a stage boundary, reallocating remaining budget, or
  launching a child before the root completes.
- Multi-depth branching where children create and fork their own archive.
- Reworking signal extraction, risk detection, or validation parsing from T003.
- Learned stage classifiers, LLM judgement, or task-specific hand-authored
  stage maps.
- Changing the number of continuations, root/child budget split, or context
  mode.

## Implementation Guidance

- Make stage assignment a pure, typed helper over T003's structured signals
  and existing candidate metadata. Keep it separate from snapshot side effects
  and continuation execution.
- `diagnosis` is valid only when the restored sandbox contains reusable state:
  for example, a reproducible failing command/test, retained logs, generated
  crash output, or an inspected database/repository state. A read-only
  `git log`, `grep`, or `cat` observation alone is not a stage-worthy snapshot
  for `context_mode=none`.
- “Validation” means an actual recognized task test or verifier result, not a
  successful shell command. Prefer partial progress over a terminal fully
  solved state when the task runner will still launch children after root
  success; record the distinction rather than treating all passing output as
  equivalent.
- Preserve the current archive and selector modes as baselines. Add a small
  `stage_aware` mode rather than changing `archive_priority` semantics.
- Do not introduce a large state machine. The stage is an interpretable label
  for snapshot eligibility and selection, not a claim that every coding task
  follows a fixed linear workflow.
- Use named ordering/priority constants and record the exact reason for each
  stage assignment, rejection, and selection decision.
- Ensure the cell key/versioning migration is backward compatible. Historical
  entries missing a stage must load and remain eligible through the documented
  fallback path.

## Suggested Starting Points

- Implement structured signals from T003 first; this ticket depends on them.
- Inspect `cell_key_for`, `ArchiveEntry`, `SnapshotArchive.add_with_result`,
  and archive persistence in `go_explore/snapshots/archive.py`.
- Inspect selector dispatch and selection metadata in
  `go_explore/snapshots/selectors.py`.
- Thread a new selector mode through `go_explore/fixed_budget.py`,
  `go_explore/experiment_runner.py`, `go_explore/continuations.py`, and
  `go_explore/cli.py` using the existing mode patterns.
- Review event/report schemas in `go_explore/events.py` and
  `go_explore/continuations.py`.

## Acceptance Criteria

- Every new archive entry produced by the structured-signal path has a primary
  stage and non-empty stage reasons, or an explicit `unknown`/fallback reason.
- States with identical changed files but different primary stages can coexist
  in the archive; same-stage replacement remains deterministic.
- `stage_aware` selects no more than one candidate per stage and never selects
  an ineligible `risky_final` state.
- Selection order follows documented stage preference while still respecting
  stronger validation/structured scores within each stage.
- Read-only discovery alone does not produce a `diagnosis` candidate for a
  snapshot-only child.
- Legacy archives without stage metadata load successfully; existing selector
  modes retain their prior behavior.
- Fixed-budget manifests, continuation reports, and events record
  `stage_aware`, primary stage, and decision reasons when that mode is used.
- `uv run pytest -q` passes.

## Test Coverage

- Unit-test pure stage assignment for verified setup, reproducible diagnosis,
  safe implementation, partial/full validation, risky final mutation, and
  read-only discovery.
- Test precedence for entries with multiple signals (for example, a safe edit
  followed by partial test progress should be `validation`; a risky edit with
  no validation should be `risky_final`).
- Test archive retention: two candidates touching the same file but in
  `setup` and `implementation` occupy distinct stage-aware cells; two in the
  same stage choose the deterministic best entry.
- Test `stage_aware` selection with more eligible stages than child slots and
  with fewer eligible stages than child slots. Assert one-per-stage, risk
  exclusion, ordering, and fallback behavior for legacy entries.
- Regression-test representative trajectories or synthetic entries based on
  `kv-store-grpc` (setup), `git-leak-recovery` (read-only discovery is not
  enough), `sqlite-db-truncate`/`sanitize-git-repo` (risk), and `regex-log`
  (unvalidated final-answer state).
- Test CLI/config/manifest serialization and continuation/event reports for
  the new mode and stage fields.

## Validation

Run:

```bash
uv run pytest \
  tests/test_archive.py \
  tests/test_selectors.py \
  tests/test_continuations.py \
  tests/test_experiment_runner.py \
  tests/test_cli.py -q
uv run pytest -q
```

Before review, replay one setup-heavy positive trajectory and one risky
negative trajectory offline. Verify archive JSON contains the expected stage
labels, and dry-run two continuations to confirm selected entries are distinct
stages with auditable reasons.

## Notes / Open Questions

- If a root fully solves the task, the continuation runner currently may still
  run children. The stage-aware selector should record a fully validated state
  accurately, but deciding whether to skip children is an experiment-runner
  policy outside this ticket.
- Stage ordering is a heuristic, not a universal law. Keep it configurable only
  if a concrete experiment requires that flexibility; avoid premature policy
  surface area.
