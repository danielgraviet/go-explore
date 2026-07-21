# Backlog

This is the source of truth for task status. Update this table when a task moves states.

Phase 2+ supersedes unfinished Phase 1 tickets. Phase 1 remains archived for historical context.

## Phase 1 Archive

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| T001 | Project map | Danny | done | - | `docs/project-map.md` |
| T002 | Smoke-test runbook | Danny | done | - | `docs/runbook.md` |
| T003 | Snapshot artifact contract | TBD | superseded | - | `docs/snapshot-artifact-contract.md` |
| T004 | Snapshot metadata audit | TBD | superseded | T003 | `docs/snapshot-metadata-audit.md` |
| T005 | Daytona snapshot cleanup runbook | TBD | superseded | T003 | `docs/daytona-snapshot-cleanup.md` |
| T006 | Continuation report polish | TBD | superseded | - | `jobs/<root>/continuation-report.json` and code/tests |
| T007 | Fixed-task comparison experiment | TBD | superseded | T006 | `docs/experiments/fixed-task-comparison.md` |
| T008 | Selector signal inventory | TBD | superseded | T004 | `docs/selector-signal-inventory.md` |
| T009 | Heuristic selector v1 | TBD | superseded | T008 | code/tests |
| T010 | Phase-1 result memo | TBD | superseded | T007 | `docs/phase-1-result-memo.md` |

## Phase 2: Measurement Substrate

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| P2-T001 | Experiment data contract | TBD | review | - | `docs/experiment-data-contract.md` |
| P2-T002 | Archive load/merge safety | TBD | review | - | code/tests |
| P2-T003 | Snapshot event log | TBD | review | P2-T001 | event JSONL and code/tests |
| P2-T004 | Budget accounting v1 | TBD | review | P2-T001 | report fields and code/tests |
| P2-T005 | Command and test signal extraction | TBD | review | P2-T001 | code/tests |
| P2-T006 | Continuation context modes spec | TBD | review | - | `docs/continuation-context-modes.md` |

## Phase 3: Baselines, Selectors, And Harness

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| P3-T001 | Selector baseline suite | TBD | review | P2-T003 | code/tests |
| P3-T002 | Start-state baseline modes | TBD | review | P2-T006 | code/tests |
| P3-T003 | Fixed-budget run planner | TBD | review | P3-T001, P3-T002, P2-T004 | manifest and code/tests |
| P3-T004 | Repeated-work metrics | TBD | review | P2-T003, P2-T005 | code/tests |
| P3-T005 | Pilot experiment runbook | TBD | review | P3-T003 | `docs/experiments/pilot-fixed-budget.md` |
| P3-T006 | Analysis tables v1 | TBD | review | P2-T001, P2-T003, P2-T004 | scripts/code/tests |

## Phase 4: Paper-Grade Experiments And Analysis

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| P4-T001 | Task set curation | TBD | backlog | P3-T005 | `docs/experiments/task-set.md` |
| P4-T002 | Main benchmark execution | TBD | backlog | P4-T001, P3-T003 | manifests, job paths, raw reports |
| P4-T003 | Paper figures v1 | TBD | backlog | P4-T002, P3-T006 | `docs/experiments/figures/` |
| P4-T004 | Failure case audit | TBD | backlog | P4-T002 | `docs/experiments/failure-case-audit.md` |
| P4-T005 | Related work citation audit | TBD | ready | - | `docs/related-work-citation-audit.md` |
| P4-T006 | Result memo and essay fill-in | TBD | backlog | P4-T003, P4-T004, P4-T005 | `docs/phase-4-result-memo.md`, `docs/essay.md` |

## Near-Term Priorities

Start with P2-T001 so sub-agents have a shared data contract. Then run P2-T002 and P2-T006 in parallel. After those land, P2-T003, P2-T004, and P2-T005 can proceed independently.
