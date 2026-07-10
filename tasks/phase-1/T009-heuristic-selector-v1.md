# T009: Heuristic Selector v1

## Goal

Implement a simple, interpretable snapshot selector that ranks continuation candidates.

## Context

Phase 1 currently uses simple ordering plus `--max-snapshots`. A heuristic selector should prefer snapshots with concrete signs of progress and avoid low-value states.

Depends on:

- T008: Selector Signal Inventory

## Scope

Implement a selector that:

- scores available snapshot candidates,
- returns a ranked list,
- records enough scoring detail for debugging,
- is covered by unit tests.

The selector should use only signals available from current artifacts unless a small missing field was explicitly identified by T008.

## Out of Scope

- Do not use learned scoring.
- Do not call a model.
- Do not optimize for all tasks.
- Do not delete unselected snapshots.

## Suggested Starting Points

- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/metrics.py`
- `go_explore/snapshots/models.py`
- `go_explore/continuations.py`
- `tests/test_snapshot_replay.py`
- `tests/test_snapshot_components.py`

## Acceptance Criteria

- Selector behavior is deterministic.
- Scores are explainable from candidate metadata.
- Tests cover ranking, ties, missing fields, and obvious high/low-value examples.
- Continuation planning can use the ranked order or has a clear follow-up ticket to wire it in.

## Validation

Run:

```bash
uv run pytest tests/test_snapshot_components.py tests/test_snapshot_replay.py -q
```

Run broader tests if continuation planning is touched:

```bash
uv run pytest tests/test_continuations.py -q
```

## Notes / Open Questions

Favor debuggability over cleverness. The first selector should be easy to disagree with and improve.
