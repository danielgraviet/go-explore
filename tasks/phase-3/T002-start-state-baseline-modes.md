# T002: Start-State Baseline Modes

## Goal

Implement the first continuation start-state modes needed for Claim 1 comparisons.

## Context

The essay compares full snapshots against compressed alternatives. Phase 3 needs enough modes to run useful pilot comparisons without blocking on every possible representation.

Depends on:

- P2-T006: Continuation Context Modes Spec

## Scope

Implement or scaffold benchmark planning for:

- fresh restart,
- diff only,
- full snapshot.

Each planned run should record `start_state_type`. Command replay and diff-plus-transcript may be documented as follow-up if they are too large for this ticket.

## Out of Scope

- Do not implement every context mode from the spec.
- Do not build the full fixed-budget planner.
- Do not run the main benchmark.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/harbor.py`
- `go_explore/cli.py`
- `tests/test_continuations.py`
- `tests/test_harbor.py`

## Acceptance Criteria

- Planner code can produce fresh restart, diff-only, and full-snapshot job commands or manifests.
- Reports or manifests distinguish `start_state_type`.
- Tests cover command planning without requiring live Daytona execution.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_harbor.py -q
```

## Notes / Open Questions

Do not overbuild diff application. If a reliable diff-only implementation requires a separate task, this ticket may create a manifest-level scaffold and document the missing executor.
