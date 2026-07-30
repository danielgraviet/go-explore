# T002 Experiment 2: Qualification Screen Report

Screen run 2026-07-30 per `docs/experiments/t002-exp2-candidate-screen-preregistration.md`.
3 independent clean repetitions per candidate, full budget `B`=500,000
(`hard_token_limit`), method=`single`, no branching. Manifests/analysis:
`docs/experiments/main-benchmark/{manifests,analysis}/t002-exp2-screen-*`.

## All 14 candidates, screen outcome

| Task | Solved | Verdict |
| --- | --- | --- |
| `git-multibranch` | 2/3 | **RETAIN** |
| `extract-elf` | 2/3 | **RETAIN** |
| `custom-memory-heap-crash` | 1/3 | **RETAIN** |
| `code-from-image` | 1/3 | **RETAIN** |
| `large-scale-text-editing` | 1/3 | **RETAIN** |
| `git-leak-recovery` | 3/3 | exclude — ceiling effect |
| `multi-source-data-merger` | 3/3 | exclude — ceiling effect |
| `build-cython-ext` | 0/3 | exclude — too hard at cap `B` |
| `regex-log` | 0/3 | exclude — too hard at cap `B` |
| `merge-diff-arc-agi-task` | 0/3 | exclude — too hard at cap `B` |
| `db-wal-recovery` | 0/3 | exclude — too hard at cap `B` |
| `polyglot-c-py` | 0/3 | exclude — too hard at cap `B` |
| `gcode-to-text` | 0/3 | exclude — too hard at cap `B` |
| `pytorch-model-recovery` | 0/3 | exclude — too hard at cap `B`, weaker signal (see note) |

**Note on `pytorch-model-recovery`**: its three failures were
`VerifierTimeoutError`, `AgentBudgetExhaustedError`, and `AgentTimeoutError`
— three different infra/timeout modes, not clean task failures. Excluded by
the numeric rule regardless, since the outcome (0/3) is the same either way,
but this is a weaker "too hard" signal than the other six 0/3 candidates.

## Final headline task list (5 tasks — approved by user 2026-07-30)

Only 5 of 14 candidates fell in the 20-80% retain band, below the
pre-registered target of up to 10. With exactly 5 retained, no further
selection trimming was needed or applied — all 5 proceed to Experiment 2
Phase B unchanged from the screen.

| Task | Solve rate | Category |
| --- | --- | --- |
| `git-multibranch` | 67% | service |
| `extract-elf` | 67% | debugging |
| `custom-memory-heap-crash` | 33% | debugging |
| `code-from-image` | 33% | artifact-heavy |
| `large-scale-text-editing` | 33% | artifact-heavy |

Category mix: 2 debugging, 2 artifact-heavy, 1 service. No setup/build task
survived (`build-cython-ext` and `polyglot-c-py`, the two setup/build
candidates, both hit 0/3).

No task was replaced or substituted after any outcome was viewed.

## Next: Phase B (headline benchmark)

5 independent repetitions × (matched clean retries + `promising_branch`,
`context_mode=none`) per selected task, same `B`=500,000, 30/35/35 split,
`archive_priority` selector — same design as Experiment 1. Approximately
5 tasks × 5 reps × 6 jobs = 150 jobs.
