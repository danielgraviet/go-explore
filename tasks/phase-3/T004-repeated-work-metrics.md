# T004: Repeated-Work Metrics

## Goal

Measure repeated setup and rediscovery work across scratch attempts and snapshot continuations.

## Context

The paper's core mechanism is not only higher solve rate. It claims snapshot branching spends less budget repeating setup and rediscovery. That claim needs metrics derived from event logs.

Depends on:

- P2-T003: Snapshot Event Log
- P2-T005: Command And Test Signal Extraction

## Scope

Implement an analysis module that computes simple repeated-work metrics from event logs:

- repeated install/setup commands,
- repeated test reproduction commands,
- repeated file discovery commands,
- repeated exact command prefixes,
- repeated commands across sibling attempts or continuations.

Store or emit run-level metrics suitable for Phase 3/4 analysis tables.

## Out of Scope

- Do not attempt semantic equivalence between arbitrary commands.
- Do not require live runs.
- Do not generate paper figures.

## Suggested Starting Points

- `go_explore/snapshots/replay.py`
- `go_explore/continuations.py`
- `tests/fixtures/atif_trajectory.json`
- `tests/test_snapshot_replay.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- Works from fixture event logs or trajectories.
- Tests cover repeated setup, repeated tests, repeated discovery, and no-repeat cases.
- Metrics are documented as heuristics.

## Validation

Run:

```bash
uv run pytest tests/test_snapshot_replay.py tests/test_continuations.py -q
```

## Notes / Open Questions

Favor transparent counts over clever scoring. The first metric should be easy to inspect and disagree with.
