# T003: Snapshot Artifact Contract

## Goal

Define the expected artifacts for a successful snapshot-aware Harbor run.

## Context

Snapshot creation crosses several systems: Harbor, the wrapped Terminus-2 agent, Daytona, and local job artifacts. A concrete artifact contract will make failures easier to debug.

Relevant docs:

- `docs/snapshot-strategy.md`
- `docs/daytona-snapshot-hook-bug.md`

## Scope

Write `docs/snapshot-artifact-contract.md` defining:

- which local files should exist after a snapshot-aware run,
- which Daytona snapshot names should exist,
- the metadata fields required per snapshot,
- how local artifacts map to remote Daytona state,
- how to tell "agent ran but wrapper did not hook" apart from "wrapper hooked but snapshot failed".

## Out of Scope

- Do not implement missing metadata fields in this ticket.
- Do not change snapshot policy behavior.
- Do not add cleanup tooling.

## Suggested Starting Points

- `go_explore/agents/snapshot_agent.py`
- `go_explore/snapshots/models.py`
- `go_explore/snapshots/stores.py`
- `go_explore/snapshots/manager.py`
- `tests/test_snapshot_agent.py`
- `tests/e2e/test_daytona_oracle.py`

## Acceptance Criteria

- The contract names required and optional artifacts.
- The contract includes a minimal example snapshot metadata object.
- The contract includes a troubleshooting table for missing artifacts.
- Any uncertainty is captured as follow-up work, not hidden.

## Validation

Compare the contract against one existing successful run if available under `jobs/`. If no successful run is available locally, state that the contract is based on code and docs only.

## Notes / Open Questions

This ticket is documentation-first. Follow-up implementation belongs in T004 or later.
