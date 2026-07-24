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
Blocked on T001.
