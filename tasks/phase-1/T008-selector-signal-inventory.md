# T008: Selector Signal Inventory

## Goal

Identify which signals are available for ranking snapshots and which are likely useful for a heuristic selector.

## Context

The first selector should be interpretable and cheap. Before implementing it, we need a clear inventory of available signals from trajectories, command output, diffs, metadata, and final results.

Depends on:

- T004: Snapshot Metadata Audit

Relevant doc:

- `docs/snapshot-strategy.md`

## Scope

Write `docs/selector-signal-inventory.md` covering:

- available per-step signals,
- available per-trial signals,
- signals that require additional instrumentation,
- likely positive indicators,
- likely negative indicators,
- suggested scoring formula for v1.

## Out of Scope

- Do not implement the selector.
- Do not use an LLM as a scorer.
- Do not add new instrumentation unless it is necessary to confirm availability.

## Suggested Starting Points

- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/metrics.py`
- `go_explore/snapshots/replay.py`
- `investigate_tbench_hooks.py`
- `tests/fixtures/atif_trajectory.json`

## Acceptance Criteria

- The inventory separates "available now" from "requires work".
- It proposes a v1 scoring formula with 5 or fewer major factors.
- It includes at least one example of a snapshot that should score high and one that should score low.
- It identifies any data quality risks.

## Validation

Apply the proposed signals manually to one existing trajectory or fixture and include the example in the doc.

## Notes / Open Questions

Keep the selector grounded in observable artifacts. Avoid persuasive but unavailable signals.
