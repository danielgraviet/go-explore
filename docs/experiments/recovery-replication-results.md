# Experiment B results

Executed 2026-08-15. Protocol:
[recovery-replication.md](recovery-replication.md).
Harness: `go-explore run-experiment --skip-children-if-root-solved`.

Do **not** pool with Experiment 2 Phase B **17/25 vs 6/25** (ledger S5)
or the earlier regex-log n=8 pilot (S7–S8).

Model: `anthropic/claude-haiku-4-5-20251001`. B=1,000,000
(`hard_token_limit`). `n_retries=3`, `n_branch_continuations=2`,
`branch_root_fraction=0.3`, `branch_context_mode=none`. Agent:
`go_explore.agents.factory:SnapshotAwareTerminus2`.

`rescued` = root failed **and** a launched child scored 1.0.

## Per-seed table

| Task | Seed | retry_solved | root_solved | children_launched | child_solved | rescued |
| --- | --- | --- | --- | --- | --- | --- |
| extract-elf | 0 | no | **yes** | no (skipped) | — | no |
| extract-elf | 1 | no | no | yes | no | no |
| extract-elf | 2 | **yes** | no | yes | **yes** | **yes** |
| extract-elf | 3 | **yes** | no | yes | **yes** | **yes** |
| extract-elf | 4 | no | **yes** | no (skipped) | — | no |
| extract-elf | 5 | **yes** | no | yes | **yes** | **yes** |
| extract-elf | 6 | no | no | yes | **yes** | **yes** |
| extract-elf | 7 | no | no | yes | no | no |
| regex-log | 0 | **yes** | no | yes | no | no |
| regex-log | 1 | no | no | yes (1 of 2) | no | no |
| regex-log | 2 | **yes** | no | yes | **yes** | **yes** |
| regex-log | 3 | no | no | yes | no | no |
| regex-log | 4 | **yes** | no | yes | no | no |
| regex-log | 5 | no | no | yes | no | no |
| regex-log | 6 | no | no | yes | no | no |
| regex-log | 7 | no | no | yes (1 of 2) | no | no |

## Headline for this experiment (not the frozen 17/25)

| Task | retry_solved / 8 | root_solved / 8 | rescued / failed-roots |
| --- | --- | --- | --- |
| extract-elf | 3/8 | 2/8 | **4/6** |
| regex-log | 3/8 | 0/8 | **1/8** |

`skip-if-root-solved` fired on extract-elf seeds 0 and 4 (root scored 1.0;
children not launched). No regex-log root solved, so every regex-log seed
launched at least one child.

regex-log seeds 1 and 7 launched only one continuation. Do not treat those
as a full two-child budget split. Harbor marked some regex-log
continuations `failed` in the execution report (seeds 3–6); rewards above
still come from each job’s `result.json`.

## What this supports

Rescue still happens on extract-elf under skip-if-root-solved (4 of 6
failed roots). On regex-log it was rare (1 of 8). Matched retry solved
3/8 on both tasks. This does **not** revise S5 and is **not** a claim
that branching beats retry.

Sources:
`docs/experiments/main-benchmark/analysis/recovery-<task>-seed-<n>/execution-report.json`
and `jobs/recovery-<task>-*/result.json`.
