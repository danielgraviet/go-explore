# T002: Main Benchmark Execution

## Goal

Run the fixed-budget benchmark across the curated task set and preserve raw artifacts.

## Context

This ticket produces the raw evidence for the paper-grade comparison between scratch retries, random branching, and promising snapshot branching.

Depends on:

- P4-T001: Task Set Curation
- P3-T003: Fixed-Budget Run Planner

## Scope

Execute the benchmark for:

- single run,
- retry from scratch,
- random snapshot branching,
- promising snapshot branching.

Include best-of-N only if judging infrastructure exists. Preserve manifests, job paths, reports, event logs, and infrastructure failures.

## Out of Scope

- Do not massage results manually.
- Do not add new methods mid-run without updating the manifest.
- Do not compute final paper claims in this ticket.

## Suggested Starting Points

- `docs/experiments/task-set.md`
- `docs/experiments/pilot-fixed-budget.md`
- `go_explore/cli.py`
- `go_explore/results.py`

## Acceptance Criteria

- Every planned run has a manifest and either completed artifacts or a recorded failure.
- Budget settings are identical across methods where required.
- Missing or failed runs are not silently dropped.

## Validation

Summarize all jobs and verify expected artifact counts. Record the exact commands used to launch the benchmark.

## Notes / Open Questions

This ticket may be expensive. If budget is constrained, run the smoke subset first and record what remains.
