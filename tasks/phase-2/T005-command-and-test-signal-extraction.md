# T005: Command And Test Signal Extraction

## Goal

Extract structured command, file-change, dependency, and test signals from agent trajectories.

## Context

Snapshot selection, repeated-work metrics, and paper figures depend on event-level signals. Current heuristics detect some changed files and interesting commands, but the experiment needs a clearer extraction layer.

Depends on:

- P2-T001: Experiment Data Contract

## Scope

Extend trajectory or replay processing to produce structured signals for:

- command execution,
- changed files,
- dependency/package installation,
- test runs and basic pass/fail signals where available.

Keep heuristics simple, deterministic, and covered by tests.

## Out of Scope

- Do not implement semantic duplicate detection.
- Do not build repeated-work metrics in this ticket.
- Do not require perfect test parsing for every ecosystem.

## Suggested Starting Points

- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/replay.py`
- `go_explore/snapshots/models.py`
- `tests/test_snapshot_replay.py`
- `tests/test_changed_files.py`
- `tests/test_snapshot_components.py`

## Acceptance Criteria

- Tests cover common test commands such as `pytest`, `npm test`, `cargo test`, and `go test`.
- Tests cover dependency install commands for common package managers where practical.
- Changed-file extraction remains backward-compatible with existing tests.
- Unknown commands are preserved without crashing extraction.

## Validation

Run:

```bash
uv run pytest tests/test_snapshot_replay.py tests/test_changed_files.py tests/test_snapshot_components.py -q
```

## Notes / Open Questions

The goal is useful signals, not a perfect shell parser. Document known false positives and false negatives.
