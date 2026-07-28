# T007 — Create start-state ablation

## Goal

Run a clean vs `diff_only` vs `full_snapshot` ablation on a small task set
without building extra context machinery first. The point is to measure how
much of the continuation benefit comes from environment state alone, versus
the full restored sandbox.

## Problem

We already have two of the three start-state shapes needed for the ablation:

- `clean`
- `full_snapshot`

`diff_only` exists only as a manifest/planning concept today. That means the
ablation is blocked on the smallest possible executor path for diff replay,
even though the planning and reporting code already understands the label.

## Efficient Plan

Keep the scope tight:

1. Implement only the minimal `diff_only` executor needed to replay the parent
   git diff onto a clean checkout.
2. Reuse the existing `plan_start_state_baselines` flow and analysis-table
   builders.
3. Do not add `command_replay` or any transcript-summary mode.
4. Run a narrow pilot first, then expand only if the artifact shape is clean.

The ablation should stay on tasks where git-tracked work is meaningful. Avoid
tasks whose useful progress lives mostly outside the repo tree.

## Recommended Task Set

Use 5-6 tasks from `docs/experiments/viability-task-set.md` that are likely to
produce a useful git diff:

- `regex-log`
- `build-cython-ext`
- `git-leak-recovery`
- `sqlite-db-truncate`
- `sanitize-git-repo`
- `large-scale-text-editing`

If one of these proves unavailable or uninformative for diff replay, replace it
with another task in the same general category that still produces tracked file
changes.

## Implementation Scope

### Diff-only executor

Add the smallest possible path that:

- creates a clean child environment,
- applies the parent diff artifact,
- records whether the diff applied cleanly,
- marks executor failures separately from task failures,
- keeps the child's prompt context as `original_task_only`.

Do not broaden this into a general replay system. This ticket is only about the
git diff case.

### Reporting

Make sure the analysis output can compare:

- solve rate,
- total tokens,
- wall-clock time,
- snapshot overhead,
- restore overhead,
- executor failures versus task failures.

Keep the start-state label explicit in the manifest and reports so the ablation
is easy to audit later.

## Deliverables

- `diff_only` start-state execution path.
- Tests covering diff planning and diff application failures.
- A small ablation run over the selected task set.
- A short memo or handoff note with the result.

## Acceptance Criteria

- `clean`, `diff_only`, and `full_snapshot` all run through the same planning
  and analysis path.
- `diff_only` is no longer manifest-only.
- The pilot produces complete rows for all planned arms, or missing rows are
  clearly attributed to infrastructure or diff-apply failure.
- The resulting tables are good enough to decide whether the ablation should be
  expanded to the rest of the viability task set.

## Validation

Before spending on the full 5-6 task batch:

- verify the new executor on one task with a known good diff,
- inspect the resulting `execution-report.json`, `run-summary.csv`, and
  `task-summary.csv`,
- confirm the diff-only child starts from the parent diff, not from a snapshot.

## Out Of Scope

- `command_replay`
- transcript-summary generation
- any new branch context mode
- full benchmark rollout

## Status

Planned. This ticket is the implementation and experiment wrapper for the
start-state ablation described in the July 27 handoff. It should be tackled
after the current primary benchmark work is stable enough to free up capacity.
