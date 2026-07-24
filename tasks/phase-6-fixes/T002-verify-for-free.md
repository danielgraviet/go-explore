# T002 — Replay-verify T001 against existing artifacts (no Harbor spend)

## Goal
Confirm the T001 fix actually changes the outcome for the known-bad case
before spending any Harbor credits.

## Source data
`jobs/phase6-viability-pilot-regex-log-promising-branch-none-promising-branch-seed-0-root/`
— has `events.jsonl` and `regex-log__agZndfb/agent/trajectory.json` on
disk already. 13 agent steps; edits to `/app/regex.txt` at steps 0, 3, 5, 7.

## Task
Write a small offline script (scratchpad, not committed) that:
1. Loads the trajectory/ATIF steps for this trial the same way
   `go_explore/snapshots/replay.py` does (`load_atif_trajectory_steps`,
   `extract_signals_from_atif_step`).
2. Re-runs `InterestingAgentStepPolicy.candidates_for_step` +
   patched `SnapshotArchive.add` over those steps in order.
3. Prints which step ends up as the accepted snapshot for the
   `{/app/regex.txt}` cell.

## Pass condition
The accepted snapshot for that cell is step 7 (or at minimum, later than
step 0) after the T001 fix — confirming the archive now retains the more
advanced edit instead of freezing on the first one.

## Files
- New scratchpad script only (e.g. `/private/tmp/.../scratchpad/replay_regex_log.py`), not part of the repo.

## Status
Done. Ran an offline replay script (scratchpad, not committed) against the
real trajectory at
`jobs/phase6-viability-pilot-regex-log-promising-branch-none-promising-branch-seed-0-root/regex-log__agZndfb/agent/trajectory.json`,
using `load_atif_trajectory_steps` + `context_from_atif_step` +
`InterestingAgentStepPolicy` + `SnapshotArchive` in step order, no Daytona.

Result: `{/app/regex.txt}` had candidates at steps 3, 6, 8, 10. With the
T001 fix, the archive retains **step 10** (the last, most-refined edit)
instead of freezing on step 3. Confirms the fix works on real trajectory
data, not just the synthetic unit test.

(Note: step numbering here doesn't match the step 0/3/5/7 seen in the
live job's `events.jsonl` in T001 — that run used the async snapshot
manager with different step bookkeeping. The mechanism and outcome are
the same: later ties now win.)

Next: T003 (live 1-seed smoke run).
