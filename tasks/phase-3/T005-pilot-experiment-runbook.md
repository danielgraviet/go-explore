# T005: Pilot Experiment Runbook

## Goal

Run or dry-run a small fixed-budget pilot and write down what happened.

## Context

Before scaling to dozens of tasks, the harness needs one concrete end-to-end check that produces manifests, reports, event logs, and analysis inputs.

Depends on:

- P3-T003: Fixed-Budget Run Planner

## Scope

Create `docs/experiments/pilot-fixed-budget.md` covering:

- selected 1-3 bounded tasks,
- exact commands,
- job paths,
- method configs,
- budget settings,
- costs if available,
- rewards and failures,
- missing fields or broken assumptions.

Use the new Phase 2/3 artifacts where available.

## Out of Scope

- Do not claim statistical significance.
- Do not run the full Terminal-Bench dataset.
- Do not tune prompts extensively.

## Suggested Starting Points

- `docs/task-selection.md`
- `docs/essay.md`
- `go_explore/cli.py`
- `go_explore/results.py`

## Acceptance Criteria

- The runbook includes exact commands and artifact paths.
- It states whether the harness worked end to end.
- It identifies the next implementation fix or experiment.
- Negative or inconclusive results are recorded clearly.

## Validation

Use `go-explore summarize-job` or equivalent result inspection for every job referenced. If live execution is not possible, include dry-run manifests and the infrastructure blocker.

## Notes / Open Questions

This ticket is about learning whether the pipeline works, not proving the research claim.
