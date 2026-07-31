# T002 Experiment 2 Phase B: Headline Results

Run complete 2026-07-31. 5 tasks, 5 seeds each, `B=1,000,000`,
`branch_context_mode=preflight_verification`. Retry = 3 fresh restarts
sharing the budget. Promising_branch = 1 root + up to 2 snapshot-restored
children sharing the budget. Per-seed comparison: did *any* attempt in that
arm solve the task.

## Headline number

| Task | Retry (any of 3) | Branch (root or child) |
| --- | --- | --- |
| git-multibranch | 5/5 | 1/5 |
| extract-elf | 4/5 | 3/5 |
| custom-memory-heap-crash | 3/5 | 1/5 |
| code-from-image | 3/5 | 1/5 |
| large-scale-text-editing | 2/5 | 0/5 |
| **Total** | **17/25 (68%)** | **6/25 (24%)** |

**Retry beat promising_branch on every task.** This is the headline result
of this run, not the one the project hypothesis expected.

## But the recovery mechanism is real

4 documented cases of a failed root being rescued by a child, using its own
separate budget share after restoring from the root's snapshot:

- `extract-elf`: seeds 1, 2, 3
- `custom-memory-heap-crash`: seed 3

Everywhere else, root and children failed together. So the mechanism
fires, just not often enough to close the gap with simple retry at this
budget and root fraction (0.3).

## Dominant failure mode: budget exhaustion, not reasoning failure

`AgentBudgetExhaustedError` accounts for nearly every failure across all 5
tasks and both methods, even at the raised `B=1,000,000`. This held for
`custom-memory-heap-crash` and `large-scale-text-editing` especially.

## Data notes

- `custom-memory-heap-crash`'s analysis tables were regenerated after the
  run — the auto-built version was stale (built mid-run, before the
  parallel seed-3/seed-4 lanes finished) and wrongly showed `solved=false`
  for both methods. Corrected tables now show `solved=true` for both,
  consistent with the job-level data above.
- `large-scale-text-editing` produced only 1 branch child per root (not 2)
  across all 5 seeds — worth checking whether its archive had too little
  state diversity to select a second candidate.

## Bottom line

At `B=1,000,000` with `branch_root_fraction=0.3`, blind retry is currently
the stronger method on this 5-task set, even though `promising_branch`
does demonstrably rescue some budget-exhausted failures. Per
`docs/headline-analysis-plan.md`, this should be reported as-is rather
than adjusted after the fact — see that doc's deferred follow-up ideas
(branch before root exhaustion, smaller root fraction, retry-to-child
reallocation) as the next things to try, in a separate labeled experiment.
