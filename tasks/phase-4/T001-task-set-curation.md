# T001: Task Set Curation

## Goal

Select the Terminal-Bench task set for the main fixed-budget experiment.

## Context

The essay needs task-level evidence, not repeated sampling on a tiny set. Task selection should avoid tasks with no headroom, high flakiness, or unreasonable cost.

Depends on:

- P3-T005: Pilot Experiment Runbook

## Scope

Write `docs/experiments/task-set.md` defining:

- primary task set,
- fallback task set,
- smoke-test subset,
- difficulty/category metadata,
- inclusion and exclusion rationale.

Target 30-50 medium or medium-hard tasks if available.

## Out of Scope

- Do not run the main benchmark.
- Do not tune tasks after seeing method outcomes.
- Do not create custom tasks.

## Suggested Starting Points

- `docs/task-selection.md`
- `go_explore/task_inventory.py`
- `tasks/research-questions.md`

## Acceptance Criteria

- The task list prioritizes diversity over repeated sampling of a tiny set.
- Too-easy, flaky, infrastructure-blocked, or too-expensive tasks are excluded with reasons.
- The doc includes a small smoke subset for validation runs.

## Validation

Use:

```bash
python -m go_explore.cli list-cached-tasks
```

or Harbor metadata inspection to verify task names and metadata.

## Notes / Open Questions

If fewer than 30 suitable tasks are available locally, document the gap and proceed with the largest defensible set.
