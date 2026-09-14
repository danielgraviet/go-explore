# Claim Ledger

Every public sentence in the blog, essay, or whitepaper must map to a
row here. If a claim is not listed as **supported**, do not write it.

Protocol freeze: the Experiment 2 Phase B headline (17/25 vs 6/25) is
never revised, averaged with later pilots, or replaced by a later
algorithm variant. See [headline-analysis-plan.md](headline-analysis-plan.md).

Aug 6 checkpoint-diagnostic canaries are **not** evidence.
[tasks/aug-6-fixes/context.md](../tasks/aug-6-fixes/context.md) records
that Daytona snapshotting was broken during those jobs.

## Supported

| ID | Claim | Evidence | Scope |
| --- | --- | --- | --- |
| S1 | Restore lineage is real: planned continuations ran from recorded Daytona snapshots. | 24/24 continuations in Experiment 1 carried a verified parent snapshot name and cell key. [docs/experiments/t002-exp1-findings.md](experiments/t002-exp1-findings.md), [docs/experiments/t002-exp1-result-memo.md](experiments/t002-exp1-result-memo.md) | 4 ceiling/near-ceiling anchors, Haiku 4.5, B=500,000, `context_mode=none` |
| S2 | On those anchors, restored continuations solved at parity with clean attempts. | Roots 11/12 (91.7%), continuations 21/24 (87.5%), retries 31/36 (86.1%); Fisher's exact p=1.0. Same memos as S1. | Not a solve-rate-advantage claim. Ceiling tasks by design. |
| S3 | A restored sandbox can freeze non-git machine state. | `fix-git` fork returned an unresolved merge conflict and a git index sitting mid-merge. [docs/archive-docs/results.md](archive-docs/results.md) | Qualitative fidelity anecdote, one task. |
| S4 | Snapshot creation and restore have measurable wall-clock cost. | Experiment 1 per-anchor sums, e.g. `kv-store-grpc` snapshot overhead 656.8s and restore 42.8s across 18 jobs. [docs/experiments/t002-exp1-result-memo.md](experiments/t002-exp1-result-memo.md) | Observed Harbor setup/snapshot intervals, not a microbenchmark. |
| S5 | Under the pre-registered headline protocol, retry beat promising_branch on every task. | git-multibranch 5/5 vs 1/5; extract-elf 4/5 vs 3/5; custom-memory-heap-crash 3/5 vs 1/5; code-from-image 3/5 vs 1/5; large-scale-text-editing 2/5 vs 0/5; **total 17/25 (68%) vs 6/25 (24%)**. [docs/experiments/t002-exp2-headline-results-memo.md](experiments/t002-exp2-headline-results-memo.md) | 5 screened tasks, 5 seeds, B=1,000,000, `branch_root_fraction=0.3`, `preflight_verification`, Haiku 4.5 |
| S6 | Children can rescue a failed root. | Headline run: extract-elf seeds 1, 2, 3; custom-memory-heap-crash seed 3. Same memo as S5; mid-run detail in [docs/early-singal-child-solve-extract-elf.md](early-singal-child-solve-extract-elf.md). | Small n. Mechanism existence, not aggregate win. |
| S7 | After the archive tie-break fix, regex-log showed 2/8 root-fail → child-solve while matched retry was 0/8. | [docs/t001-t005-phase6-fixes-results.md](t001-t005-phase6-fixes-results.md) | Different protocol from S5. Do not pool with 17/25. |
| S8 | Continuing past an already-solved root can regress. | regex-log n=8 seeds 0 and 2: root solved, child restored a mid-trajectory snapshot and failed. Same memo as S7. | Motivates skip-if-root-solved. |
| S9 | Budget exhaustion is the dominant headline failure mode. | Mid-run rates 50–87% across the five headline tasks at B=1,000,000. [docs/headline-analysis-plan.md](headline-analysis-plan.md), [docs/headline-blockers.md](headline-blockers.md), S5 memo. | Haiku 4.5, this budget split. |
| S10 | Restoring a wrong partial solution can trap the child. | regex-log children restored `/app/regex.txt` edits and failed the hidden verifier; context_mode=none also failed from the same snapshot. [docs/experiments/failure-case-audit.md](experiments/failure-case-audit.md), [docs/experiments/context-ablation-smoke-20260722.md](experiments/context-ablation-smoke-20260722.md) | Smoke / ablation, not headline n. |
| S11 | Inherited parent summaries are expensive and are not sufficient to explain branch failure. | Same snapshot: `none` used 5,254 tokens; `parent_summary` 127,274; `critical_parent_summary` 109,298; all failed. Context-ablation memo in S10. | One task, one snapshot. |
| S12 | Children can spend budget re-discovering how to verify. | Observed PATH/pytest/`/tests/test.sh` archaeology; one child 26 steps / 190k tokens vs a winning retry of 11 steps / 90k. [docs/headline-blockers.md](headline-blockers.md) | Trajectory inspection, not a table metric. |
| S13 | Children can rubber-stamp a parent's wrong answer. | Early `chess-best-move`: child read `/app/move.txt`, declared done from "previous analysis," quit in 3 steps vs root's 24. [docs/archive-docs/results.md](archive-docs/results.md). Closest later pattern: regex-log local tests vs hidden verifier. [docs/experiments/failure-case-audit.md](experiments/failure-case-audit.md) | Qualitative. |
| S14 | Heuristic selectors can score claimed completion or generic success as if it were a real test. | Archive scored a bare completion claim as `VERIFIER`; KV probe treated pip "Successfully installed" as one passed test. [docs/headline-blockers.md](headline-blockers.md), [docs/phase6-failure-analysis.md](phase6-failure-analysis.md) | Bugs found and later fixed. Historical archives may still contain the old labels. |
| S15 | The archive can freeze on the first edit to a file when scores tie. | regex-log `/app/regex.txt` edited at steps 0, 3, 5, 7 all scoring 1.25; only step 0 kept until tie-break was reversed. [docs/t001-t005-phase6-fixes-results.md](t001-t005-phase6-fixes-results.md) | Fixed. Cite as a selector failure mode, not current code. |
| S16 | Harbor will ignore a custom agent import path if `--agent terminus-2` is also set. | [docs/daytona-snapshot-hook-bug.md](daytona-snapshot-hook-bug.md) | Engineering pitfall. |
| S17 | Headline tasks were screened into a 20–80% solve-rate band, not sampled at random. | [docs/experiments/t002-exp2-screen-report.md](experiments/t002-exp2-screen-report.md), [docs/experiments/t002-exp2-candidate-screen-preregistration.md](experiments/t002-exp2-candidate-screen-preregistration.md) | Must be disclosed. |
| S18 | Early runs labeled token budgets `planning_only`; later headline/Exp 1 runs used `hard_token_limit`. | [docs/phase6-failure-analysis.md](phase6-failure-analysis.md) §8, Experiment 1 result memo. | Do not mix planning-only rows into headline rates. |
| S19 | On extract-elf Claim 1 seeds with valid diffs (1–4), compressed start states solved the remaining 200k cap and full snapshot did not. | Seeds 1, 3, 4: `diff_only` and/or `diff_transcript` reward 1.0, snapshot budget-exhausted. Seed 2: `command_replay` 1.0, snapshot budget-exhausted. [docs/experiments/claim1-representation-ablation-results.md](experiments/claim1-representation-ablation-results.md) | n=4 complete 5-way rows, Haiku 4.5. extract-elf seed 0 snapshot-solved but its diff arms are invalid. |
| S20 | Under skip-if-root-solved, extract-elf rescued 4/6 failed roots; regex-log rescued 1/8. Matched retry was 3/8 on both tasks. | [docs/experiments/recovery-replication-results.md](experiments/recovery-replication-results.md) | B=1e6, 8 seeds/task, `context_mode=none`. Do not pool with S5 17/25. |
| S21 | On staged-service-repair, same planted checkpoint and 200k remaining cap, full snapshot solved 4/5 seeds; `diff_only` 0/5 and `clean` 0/5. | [docs/experiments/env-progress-ablation-results.md](experiments/env-progress-ablation-results.md) | One custom task, Haiku 4.5, 5 seeds. Inclusion: lot not in `parent.diff`. Do not pool with S5 or S19. |
| S22 | On staged-service-repair, when retry and promising_branch **both** start from the planted warehouse snapshot, the 1-seed practice race was dual-ceiling (retry 1/1, branch 1/1); scored n=5 was not run. | [docs/experiments/env-progress-search-results.md](experiments/env-progress-search-results.md) | B=600k, skip-if-root-solved, Haiku 4.5. Children skipped because the root solved. Do not pool with S5 or S21. Not a branching-beats-retry claim. |

## Not supported — do not write

| ID | Forbidden claim | Why |
| --- | --- | --- |
| N1 | Snapshot branching solves more tasks than retry. | Refuted by S5 under the headline protocol. |
| N2 | Full snapshots beat git diffs, transcripts, or command replay **on Terminal-Bench**. | Experiment A ran. Valid extract-elf rows show compressed arms solving more often than snapshot (S19). regex-log diff arms were executor failures. S21 is a different task. |
| N3 | Promising selection beats random selection as a headline result. | Figure table exists but paired n is weak; [docs/experiments/figures/figure-status.csv](experiments/figures/figure-status.csv) shows 1 source row for promising-vs-random lift. |
| N4 | We reduced repeated setup. | `repeated_setup_score` is unsupported unless a repeated-work report is supplied. Exp 1 memo; failure-case audit. |
| N5 | Oracle selection shows large headroom. | `oracle_gap` is `deferred_no_observed_signal`. |
| N6 | Context removal fixes continuation failures. | S11: `none` still failed. |
| N7 | Aug 6 diagnostic canaries show restore vs retry. | Snapshotting was broken. |
| N8 | Pool regex-log 2/8 with headline 6/25. | Different budget, context mode, selector, and task set. |
| N9 | Fill the original abstract's `[X%]` / `[Y%]` from a subset that looked good. | Explicitly forbidden by the publication plan. |
| N10 | Pool Experiment E (S21) with headline 17/25 or with extract-elf S19. | Different task, planted checkpoint, and question. |
| N11 | Pool Experiment F (S22) with headline 17/25 or with S21. | Different question: F is search from a planted start; E is representation; S5 is Terminal-Bench. |

## Pending (Experiment A / B / E / F)

| ID | Claim | Unlocks when |
| --- | --- | --- |
| P1 | Full snapshots are better / worse / tied with compressed start states at a matched remaining cap. | **Filled as S19** (worse on valid extract-elf 5-way rows; regex-log diffs invalid). Do not upgrade to “snapshots beat compressed.” |
| P2 | Paired rescue rate on extract-elf and regex-log with skip-if-root-solved. | **Filled as S20.** Report 4/6 and 1/8, not a pooled % with 17/25. |
| P3 | On an env-progress task, full snapshot vs `diff_only` vs `clean` at a matched remaining cap. | **Filled as S21** (snapshot 4/5, diff 0/5, clean 0/5 on staged-service-repair). |
| P4 | On staged-service-repair, retry vs promising_branch when **both** start from the planted warehouse snapshot. | **Filled as S22** (dual-ceiling canary; scored n=5 not run). Do not pool with S5 or S21. |

## Required disclosures

- Single model tier: `anthropic/claude-haiku-4-5-20251001`.
- Unit of generalization is the task; n is small.
- Snapshot/restore overhead is Harbor-observed, not isolated.
- Daytona snapshot cap (~100 per account) constrained concurrency.
- Infra failures (prune-too-early, `EnvironmentStartTimeoutError`, Harbor import-path bug) are costs of the method when they affected a reported row, and must be labeled when they did not.
