# Failure Taxonomy

Coded from existing trajectories and memos. This is the paper's mechanistic
contribution until Experiment A/B land. Do not invent rates that are not
in [docs/claim-ledger.md](claim-ledger.md).

## Codes

| Code | Name | What it looks like | Primary evidence |
| --- | --- | --- | --- |
| F1 | Budget fragmentation | Root burns its share; children burn theirs; retry keeps full independent draws. Dominant exception is `AgentBudgetExhaustedError`. | Ledger S5, S9 |
| F2 | Wrong-state attractor | Restore faithfully returns a bad artifact (`/app/regex.txt`, `/app/move.txt`). The child edits around it instead of re-deriving. | Ledger S10, S13 |
| F3 | Handoff tax | Child spends turns re-establishing how to run the real verifier (`python` PATH, `pytest`, `/tests/test.sh`) before new work. | Ledger S12 |
| F4 | False completion | Agent (root or child) declares done after a local check that is not the official verifier, or after a generic "are you sure?" confirm. | Ledger S13, S14; [docs/headline-blockers.md](headline-blockers.md) items 2 and 4 |
| F5 | Unverified selector | Archive ranks claimed completion, generic "success" text, or first tied file-edit as promising. | Ledger S14, S15 |
| F6 | Solved-root regression | Children launch after the root already scored 1.0 and can unsolve the chain. | Ledger S8 |
| F7 | Thin archive | Not enough distinct high-quality cells to fill requested child slots. | Headline `large-scale-text-editing`: 1 child per root on every seed. S5 memo |
| F8 | Infra / restore noise | Snapshot missing after premature prune; `EnvironmentStartTimeoutError`; Harbor built-in agent used instead of the wrapper. | [docs/headline-blockers.md](headline-blockers.md) item 6; ledger S16 |

## How to use in writing

Lead with F1 and F2. They explain why restore can be correct as infrastructure
and still lose as a search policy. F3 and F4 are the handoff story for the
Daytona blog. F5–F8 are engineering lessons, not algorithm refutations,
unless they contaminated a reported row — in which case label that row.

## Coding rule for later trajectories

Assign one primary code per failed run. Secondary codes are allowed.
Do not code a run as F2 if the child never reached the verifier (use F8
or F1). Do not code F3 unless the trajectory shows verification-tooling
work before task work.
