# T005: Daytona Snapshot Cleanup Runbook

## Goal

Document a safe way to list, inspect, and clean up Go-Explore Daytona snapshots.

## Context

Snapshot-heavy experiments can leave many remote snapshots. Before running larger experiments, contributors need an explicit cleanup path that avoids deleting unrelated Daytona state.

Depends on:

- T003: Snapshot Artifact Contract

## Scope

Write `docs/daytona-snapshot-cleanup.md` covering:

- how Go-Explore snapshot names are prefixed,
- how to list candidate snapshots,
- what metadata to check before deletion,
- a safe manual cleanup procedure,
- risks and safeguards.

If a CLI helper already exists or is easy to add safely, document it. Otherwise, keep this as a manual runbook.

## Out of Scope

- Do not delete snapshots as part of the ticket unless explicitly approved by the project lead.
- Do not add automated deletion without a dry-run mode.
- Do not touch non-Go-Explore Daytona resources.

## Suggested Starting Points

- `go_explore/snapshots/backends.py`
- `go_explore/snapshots/live.py`
- `docs/daytona-snapshot-hook-bug.md`

## Acceptance Criteria

- The runbook makes deletion opt-in and dry-run-first.
- It explains the naming convention used by Go-Explore snapshots.
- It includes a checklist before deletion.
- It records any SDK/API limitations discovered.

## Validation

If live Daytona inspection is performed, record the exact command or script used and the number of matching snapshots found.

Do not include secrets or account-specific identifiers in the doc.

## Notes / Open Questions

This is partly operational hygiene. Prefer safety over convenience.
