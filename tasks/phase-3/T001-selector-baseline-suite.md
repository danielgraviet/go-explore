# T001: Selector Baseline Suite

## Goal

Implement selector baselines needed to compare list order, random branching, heuristic branching, and oracle upper bounds.

## Context

The essay's Go-Explore claim depends on showing that promising-state selection beats random-state selection. The system needs selectable, logged policies rather than one implicit archive order.

Depends on:

- P2-T003: Snapshot Event Log

## Scope

Add selector modes for:

- list order,
- seeded random,
- current heuristic/archive priority,
- oracle placeholder using precomputed labels when available.

Record selector mode and reasons in selection events or continuation reports.

## Out of Scope

- Do not implement learned or LLM-based selection.
- Do not invent oracle labels.
- Do not change snapshot creation policy unless needed for metadata.

## Suggested Starting Points

- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/policies.py`
- `go_explore/continuations.py`
- `go_explore/cli.py`
- `tests/test_archive.py`
- `tests/test_continuations.py`
- `tests/test_snapshot_components.py`

## Acceptance Criteria

- CLI or config can choose selector mode for continuation planning.
- Random selector is seedable and reproducible.
- Oracle mode fails clearly when labels are absent.
- Tests cover list order, seeded random, heuristic ordering, and missing oracle labels.

## Validation

Run:

```bash
uv run pytest tests/test_archive.py tests/test_continuations.py tests/test_snapshot_components.py -q
```

## Notes / Open Questions

Keep the selector interface small. The first goal is comparable baselines, not an optimal selector.
