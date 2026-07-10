# T004: Snapshot Metadata Audit

## Goal

Audit current snapshot metadata against the artifact contract and identify the smallest useful improvements.

## Context

Before improving snapshot selection, we need to know what information is actually available per snapshot and whether it is enough to rank continuation candidates.

Depends on:

- T003: Snapshot Artifact Contract

## Scope

Write `docs/snapshot-metadata-audit.md` with:

- current metadata fields,
- missing fields needed for selection,
- missing fields needed for debugging,
- fields that are expensive or unavailable,
- recommended next implementation tickets.

If a small missing field is trivial to add and test, it may be included in this ticket, but keep the audit as the primary deliverable.

## Out of Scope

- Do not build the selector.
- Do not redesign the snapshot model.
- Do not add learned scoring.

## Suggested Starting Points

- `go_explore/snapshots/models.py`
- `go_explore/snapshots/stores.py`
- `go_explore/snapshots/metrics.py`
- `go_explore/snapshots/replay.py`
- `jobs/<successful-snapshot-run>/`

## Acceptance Criteria

- The audit maps actual fields to the contract from T003.
- It identifies which fields are enough for a heuristic selector v1.
- It lists concrete follow-up changes, each small enough to become a ticket.
- If code changes are made, tests are included.

## Validation

Run relevant unit tests if code changes are made:

```bash
uv run pytest tests/test_snapshot_agent.py tests/test_snapshot_manager.py -q
```

If only documentation changes are made, no test run is required.

## Notes / Open Questions

Pay attention to fields that help compare snapshots across different trials, not just within one trajectory.
