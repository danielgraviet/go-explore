# T006: Analysis Tables V1

## Goal

Generate normalized task-level and run-level tables from experiment artifacts.

## Context

Phase 4 figures and the final essay need a reproducible path from raw job outputs to tables. This ticket creates the first version of that analysis layer.

Depends on:

- P2-T001: Experiment Data Contract
- P2-T003: Snapshot Event Log
- P2-T004: Budget Accounting V1

## Scope

Implement scripts or modules that convert reports and event logs into:

- task-level rows,
- run-level rows,
- warnings for missing optional fields.

Outputs may be CSV or JSON as specified by `docs/experiment-data-contract.md`.

## Out of Scope

- Do not generate final paper plots.
- Do not run the main benchmark.
- Do not silently impute missing costs or tokens.

## Suggested Starting Points

- `go_explore/results.py`
- `go_explore/continuations.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- Output includes method, task, solved status, budget, cost if available, snapshots created/forked, and lineage.
- Tests cover table generation from fixtures.
- Missing optional fields produce warnings or explicit unknowns.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py -q
```

## Notes / Open Questions

Keep table generation deterministic so plots can be regenerated from the same raw artifacts.
