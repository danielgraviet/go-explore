# T002 Experiment 1: Does Snapshot Restore Match a Clean Attempt?

**Question**: at the same enforced token budget, does a Go-Explore
continuation (restored from a snapshot) solve at the same rate as a single
clean attempt (root) or an independent clean retry?

**Setup**: 4 stable anchors (`kv-store-grpc`, `pypi-server`,
`nginx-request-logging`, `log-summary-date-ranges`) × 3 independent
repetitions, `promising_branch` (`context_mode=none`) vs. matched clean
retries, all under one enforced aggregate budget `B`=500,000
(`hard_token_limit`, T001). Full detail: `t002-exp1-result-memo.md`.

## Result

| Arm | n | Solved | Rate |
| --- | --- | --- | --- |
| Root (single clean attempt) | 12 | 11 | 91.7% |
| Continuation (restored) | 24 | 21 | 87.5% |
| Retry (independent clean attempt) | 36 | 31 | 86.1% |

Fisher's exact test: continuation vs. root p=1.0, continuation vs. retry
p=1.0 — **statistically indistinguishable** at this sample size.

Restore lineage: **24/24 (100%)** continuations verified against a real
Daytona snapshot.

## Per-anchor breakdown

| Anchor | Root | Continuation | Retry |
| --- | --- | --- | --- |
| `kv-store-grpc` | 2/3 | 5/6 | 6/9 |
| `pypi-server` | 3/3 | 6/6 | 9/9 |
| `nginx-request-logging` | 3/3 | 6/6 | 8/9 |
| `log-summary-date-ranges` | 3/3 | 4/6 | 8/9 |

- `pypi-server` / `nginx-request-logging`: root and continuation tied at
  ceiling — the clean validation case.
- `kv-store-grpc`: continuation (83%) beat both root and retry (67% each) —
  restoring state helped on the one anchor still token-constrained even at
  B=500,000 (it uses 2-2.5x the tokens of the other three).
- `log-summary-date-ranges`: continuation (67%) underperformed root (100%),
  but n=6 — one job flips this by 17 points, not a reliable signal.

## Verdict

**Supported.** Restoration is reliable (100% verified lineage) and
continuations solve at parity with clean attempts at matched budget — no
detectable advantage or disadvantage. This is the expected result for a
restore-reliability check on ceiling-effect anchors; it is **not** a
solve-rate-advantage claim. That question is Experiment 2's, on
harder, non-ceiling tasks.
