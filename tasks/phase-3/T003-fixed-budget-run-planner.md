# T003: Fixed-Budget Run Planner

## Goal

Create a planner that expands a fixed-budget experiment config into concrete runs and dry-run commands.

## Context

The essay's comparisons are only meaningful under equal budget. A planner should make budget splits explicit before live runs execute.

Depends on:

- P3-T001: Selector Baseline Suite
- P3-T002: Start-State Baseline Modes
- P2-T004: Budget Accounting V1

## Scope

Implement a planner that supports:

- single long run,
- retry from scratch,
- random snapshot branching,
- promising snapshot branching.

The planner should output a manifest containing task, method, seed, model, budget, planned jobs, and commands.

## Out of Scope

- Do not enforce provider-side hard token limits unless the repo already supports it.
- Do not implement best-of-N judging unless it already exists.
- Do not run the main experiment.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/harbor.py`
- `go_explore/cli.py`
- `tests/test_continuations.py`
- `tests/test_harbor.py`

## Acceptance Criteria

- Planner supports dry-run manifest generation.
- Budget splits are visible in the manifest.
- Tests cover budget splits, seeds, method names, and command generation.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_harbor.py -q
```

## Notes / Open Questions

Planning-level budget enforcement is sufficient for this ticket. Runtime enforcement can be a later task if Harbor/model APIs expose a clean control.
