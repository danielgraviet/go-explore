# T002: Archive Load/Merge Safety

## Goal

Make archive persistence safe when a new `ArchiveStore` writes to an existing `archive.json`.

## Context

The archive currently stores the best snapshot per cell and writes `jobs/<job>/archive.json`. The next experiments will run multiple roots and continuations against shared job directories, so archive writes must not accidentally discard existing entries.

Relevant docs:

- `docs/archive-docs/code.md`
- `docs/archive-docs/results.md`

## Scope

Update archive persistence so:

- an `ArchiveStore` created with a path can load an existing archive,
- existing entries survive a later `put()`,
- replacement rules for same-cell entries remain score-based,
- concurrency limitations are documented if file locking is not implemented.

Add or update unit tests around archive load, merge, save, and same-cell replacement behavior.

## Out of Scope

- Do not implement distributed locking.
- Do not redesign cell scoring.
- Do not delete or clean up remote Daytona snapshots.

## Suggested Starting Points

- `go_explore/snapshots/archive.py`
- `go_explore/agents/snapshot_agent.py`
- `tests/test_archive.py`

## Acceptance Criteria

- Existing archive entries survive a new `ArchiveStore.put()`.
- Missing archive files still produce a usable empty archive.
- Same-cell replacement still keeps the higher-scoring entry.
- Tests cover missing archive, existing archive, and same-cell replacement after load.

## Validation

Run:

```bash
uv run pytest tests/test_archive.py -q
```

If snapshot manager wiring changes, also run:

```bash
uv run pytest tests/test_snapshot_manager.py -q
```

## Notes / Open Questions

If true concurrent writers remain unsafe, document that explicitly in the code or a short note so benchmark runners avoid `n_concurrent > 1` for archive-writing jobs until locking exists.
