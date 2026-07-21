# T004: Budget Accounting V1

## Goal

Add normalized budget and cost fields to continuation reports and run summaries.

## Context

The paper's headline comparisons require fixed budget. The system needs explicit accounting for model tokens, cost, wall-clock runtime, snapshot overhead, and restore/fork overhead where available.

Depends on:

- P2-T001: Experiment Data Contract

## Scope

Add budget fields to reports or summary structures for:

- input tokens,
- output tokens,
- total tokens,
- model cost if available,
- wall-clock runtime,
- snapshot creation overhead,
- restore/fork overhead,
- missing/unknown metric state.

Pull from Harbor artifacts and existing snapshot timing data where available.

## Out of Scope

- Do not build the full fixed-budget planner.
- Do not estimate provider pricing when cost is unavailable.
- Do not require every provider/model to expose cost.

## Suggested Starting Points

- `go_explore/results.py`
- `go_explore/continuations.py`
- `go_explore/snapshots/metrics.py`
- `tests/test_continuations.py`
- `tests/test_snapshot_timing.py`

## Acceptance Criteria

- Continuation reports include budget fields without breaking existing parsing.
- Missing cost or token data is represented explicitly as unknown/null, not as zero.
- Tests cover complete metrics, partial metrics, and missing metrics.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_snapshot_timing.py -q
```

## Notes / Open Questions

Favor additive report fields. If existing Harbor artifacts vary by agent/provider, document the observed variants in the test fixtures or code comments.
