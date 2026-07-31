# Early Signal: Child Solves Where Root Fails (extract-elf)

Snapshot taken mid-run, 2026-07-31, during Experiment 2 Phase B
(`t002-exp2-headline-*`, `B=1,000,000`, `branch_context_mode=preflight_verification`).
Run was still in progress at time of writing — numbers below will grow.

## extract-elf: promising_branch root vs. children

| Seed | Root | Child (snapshot-0) | Child (snapshot-1) |
| --- | --- | --- | --- |
| 0 | fail (budget exhausted) | fail (budget exhausted) | — |
| 1 | fail (budget exhausted) | **solve** | fail (budget exhausted) |
| 2 | fail (budget exhausted) | **solve** | fail (`AddTestsDirError`) |
| 3 | fail (budget exhausted) | **solve** | fail (budget exhausted) |

**3 of 3 completed seeds where the root failed on budget exhaustion had a
child (`snapshot-0`) go on to solve the task**, using its own separate
token share after restoring from the root's archived snapshot with
`preflight_verification` context. This is the core Claim 2 mechanism:
recovery from a dead-end parent within the same total fixed budget.

## Caveats

- Signal is currently isolated to `extract-elf`. Other tasks
  (`git-multibranch`, `custom-memory-heap-crash`, `large-scale-text-editing`)
  show all-failing roots and all-failing children on every completed seed
  so far — several seeds still in progress.
- `code-from-image` seed 1 shows the inverse: root solved, both children
  failed on infra errors (`EnvironmentStartTimeoutError`,
  `DaytonaValidationError`), not budget or reasoning failures — not
  evidence against the effect, just noise.
- Only `snapshot-0` (first branch draw) has recovered anything so far;
  `snapshot-1` has not solved in any seed yet.
- Small n (3 recoveries). Directionally strong and consistent, not yet
  statistically established — full 5-task, 5-seed run needs to finish
  before citing this formally.

## Source

Pulled from `jobs/t002-exp2-headline-*/result.json` via ad hoc inspection
script, not yet part of `build-analysis-tables` output.
