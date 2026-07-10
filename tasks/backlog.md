# Backlog

This is the source of truth for task status. Update this table when a task moves states.

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| T001 | Project map | Danny | done | - | `docs/project-map.md` |
| T002 | Smoke-test runbook | TBD | ready | - | `docs/runbook.md` |
| T003 | Snapshot artifact contract | TBD | ready | - | `docs/snapshot-artifact-contract.md` |
| T004 | Snapshot metadata audit | TBD | ready | T003 | `docs/snapshot-metadata-audit.md` |
| T005 | Daytona snapshot cleanup runbook | TBD | backlog | T003 | `docs/daytona-snapshot-cleanup.md` |
| T006 | Continuation report polish | TBD | ready | - | `jobs/<root>/continuation-report.json` and code/tests |
| T007 | Fixed-task comparison experiment | TBD | backlog | T006 | `docs/experiments/fixed-task-comparison.md` |
| T008 | Selector signal inventory | TBD | backlog | T004 | `docs/selector-signal-inventory.md` |
| T009 | Heuristic selector v1 | TBD | backlog | T008 | code/tests |
| T010 | Phase-1 result memo | TBD | backlog | T007 | `docs/phase-1-result-memo.md` |

## Near-Term Priorities

T001 is done. Next, do T002 and T003 so contributors have both a runbook and a snapshot artifact contract.

After that, move to T006 if the continuation path is the highest priority, or T004 if snapshot observability is still unclear.
