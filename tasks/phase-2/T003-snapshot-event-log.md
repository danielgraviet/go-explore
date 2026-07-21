# T003: Snapshot Event Log

## Goal

Add an append-only event log for snapshot lifecycle and continuation lineage.

## Context

The essay requires mechanistic claims about which snapshots were created, selected, and forked. Archive metadata is not enough by itself because selection and continuation events also need durable records.

Depends on:

- P2-T001: Experiment Data Contract

## Scope

Implement event logging for:

- `snapshot_created`,
- `snapshot_selected`,
- `continuation_started`.

Each event should include the identifiers and metadata required by `docs/experiment-data-contract.md`, including run/job identifiers, trial name, step ID where available, snapshot name, cell key, score, selector reasons where available, parent snapshot, and timing where available.

Write events under the relevant job directory with a stable filename.

## Out of Scope

- Do not implement all command/test/dependency events in this ticket.
- Do not redesign the continuation report.
- Do not run a live benchmark.

## Suggested Starting Points

- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/manager.py`
- `go_explore/continuations.py`
- `tests/test_archive.py`
- `tests/test_continuations.py`
- `tests/test_snapshot_manager.py`

## Acceptance Criteria

- Snapshot creation events can be matched to archive entries.
- Continuation planning or execution records which snapshots were selected.
- Continuation startup records the parent snapshot and child job/run identifier.
- Unit tests verify event shape and append behavior.

## Validation

Run:

```bash
uv run pytest tests/test_archive.py tests/test_continuations.py tests/test_snapshot_manager.py -q
```

## Notes / Open Questions

Prefer JSONL for append-only events. If a run lacks a stable identifier today, use the best available job/trial/snapshot identifiers and note any remaining gap.
