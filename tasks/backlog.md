# Backlog

This is the source of truth for task status. Update this table when a task moves states.

Phase 2+ supersedes unfinished Phase 1 tickets. Phase 1 remains archived for historical context.

Phase 5 is inserted after the `regex-log-r3` smoke result and should be completed before treating Phase 4 benchmark outputs as paper-grade evidence. Phase 4 remains the paper/benchmark phase, but its analysis tickets should wait for the corrective context-mode and budget-labeling work below.

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
| P4-T001 | Task set curation | TBD | review | P3-T005 | `docs/experiments/task-set.md` |
| P4-T002 | Main benchmark execution | TBD | review | P4-T001, P3-T003 | manifests, job paths, raw reports |
| P4-T003 | Paper figures v1 | TBD | review | P4-T002, P3-T006 | `docs/experiments/figures/` |
| P4-T004 | Failure case audit | TBD | review | P4-T002 | `docs/experiments/failure-case-audit.md` |
| P4-T005 | Related work citation audit | TBD | ready | - | `docs/related-work-citation-audit.md` |
| P4-T006 | Result memo and essay fill-in | TBD | backlog | P4-T003, P4-T004, P4-T005 | `docs/phase-4-result-memo.md`, `docs/essay.md` |

## Phase 5: Context Ablations And Corrective Benchmarking

| ID | Title | Owner | Status | Depends On | Artifact |
| --- | --- | --- | --- | --- | --- |
| P5-T001 | Regex-log R3 result audit | TBD | review | completed `phase4-smoke-regex-log-r3` run | `docs/experiments/regex-log-r3-audit.md` |
| P5-T002 | Explicit context mode controls | TBD | review | P2-T006, P5-T001 | code/tests |
| P5-T003 | Critical parent summary mode | TBD | review | P5-T002 | code/tests, docs |
| P5-T004 | Clean parent summary baseline | TBD | review | P5-T002 | code/tests |
| P5-T005 | Snapshot probe scoring | TBD | review | P5-T001 | code/tests |
| P5-T006 | Budget enforcement or explicit labels | TBD | review | P3-T003, P3-T006 | code/tests, docs |
| P5-T007 | Context ablation smoke run | TBD | review | P5-T002, P5-T003, P5-T006 | smoke jobs, analysis tables, result memo |

## Near-Term Priorities

Start with P5-T001 to preserve the `regex-log-r3` evidence. Then run P5-T002 and P5-T006 in parallel. After P5-T002 lands, P5-T003 and P5-T004 can proceed independently. Run P5-T007 only after context modes and budget labeling are merged.
