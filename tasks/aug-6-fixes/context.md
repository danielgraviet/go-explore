# Aug 6 handoff

- T001 (grounded preflight selector) and T004 (checkpoint handoff diagnostic)
  are implemented; the full suite passed: `326 passed, 9 skipped`.
- T004 adds `go-explore checkpoint-diagnostic`, which compares a restored child
  with a clean retry at the same remaining token cap. The original root is
  observation-only because its live context cannot yet be cap-matched.
- A small live canary was launched in tmux session
  `aug6-checkpoint-diagnostic-canary`, latest job prefix
  `aug6-checkpoint-diagnostic-canary-r2`, but Daytona snapshotting is currently
  broken. Do not interpret either canary as an experiment result.
- Once Daytona snapshots work again: run a small root that produces an archived
  snapshot, then invoke `checkpoint-diagnostic` on that exact snapshot and
  inspect the resulting `checkpoint-diagnostic.json` before launching a full
  diagnostic.
