# T002: Viability Task Set

## Goal

Choose a small but informative task set for deciding whether sandbox snapshot continuation is viable for coding agents.

## Context

The current evidence is too narrow. `fix-git` is a positive canary, while `regex-log` is a strong negative case. We need tasks that exercise different ways snapshotting might help or hurt.

## Scope

Write `docs/experiments/viability-task-set.md` with 8-12 Terminal-Bench tasks grouped by expected snapshot value:

- easy canary,
- known hard negative,
- long setup or dependency-heavy tasks,
- tasks with reusable exploration state,
- tasks with final-answer-file risk,
- tasks where clean retry sometimes succeeds.

For each task, include the reason for inclusion, expected failure mode, and stop criteria for a pilot run.

## Out of Scope

- Do not run the task set.
- Do not optimize the task list for favorable results.
- Do not include tasks that require unsupported credentials or manual intervention.

## Suggested Starting Points

- `docs/experiments/task-set.md`
- `docs/experiments/failure-case-audit.md`
- `docs/experiments/regex-log-r3-audit.md`
- Terminal-Bench cached task inventory if available.

## Acceptance Criteria

- The doc lists 8-12 tasks with rationale.
- The task set includes both `fix-git` and `regex-log`.
- Each task has an expected snapshot-help hypothesis and a likely failure mode.
- The doc recommends a 2-3 task pilot subset before the full batch.

## Validation

Cross-check task names against the cached task inventory or a dry-run Harbor listing. Include the exact command used for validation in the doc.

## Notes / Open Questions

Prefer tasks where logs, build artifacts, local tests, or environment setup could plausibly be reusable. Avoid tasks that are pure one-shot answer writing unless they are included as final-answer-file risk controls.
