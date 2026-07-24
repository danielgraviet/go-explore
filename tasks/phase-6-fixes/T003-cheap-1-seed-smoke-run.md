# T003 — 1-seed live smoke run to confirm T001 in a real trial

## Goal
Confirm the T001 fix holds in a live run, not just replay of an existing
trajectory (replay in T002 can't validate Daytona snapshot creation/accept
plumbing end to end).

## Command
Follow `docs/runbook.md` "Fixed-Budget Smoke Experiments" flow, single task,
single seed, root only first:

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name regex-log \
  --n-tasks 1 \
  --job-name t003-regex-log-root-smoke \
  --export-traces
```

Then inspect `jobs/t003-regex-log-root-smoke/archive.json` and
`events.jsonl` directly (no need to run continuations for this check).

## Pass condition
For any cell with multiple `file_edit` candidates to the same file set, the
accepted entry is the latest one that scored >= prior candidates, not
frozen on the first touch. If the trajectory doesn't happen to produce
repeat edits to the same file this run, that's inconclusive, not a fail —
note it and rely on T002's replay result plus T004.

## Cost
One Daytona root job, haiku model — cheap. Do not run continuations here;
that's covered in T004.

## Status
Done. Ran `jobs/t003-regex-log-root-smoke` (single Daytona root, haiku,
regex-log). Trial completed (reward 0.0 — task not solved this attempt,
expected variance on a single run, not what this ticket tests).

Archive produced 2 cells from 3 candidates (steps 5, 7, 9). The
`<discovery>` cell got two candidates: step 5 (score 1.0) then step 9
(score 1.0) — a tie. Post-T001, the archive holds **step 9**
(`events.jsonl` confirms `archive_accepted: true` for both, and
`archive.json` only has the later one). Pre-fix, step 9 would have been
rejected (`incumbent.score >= score` was true). This confirms the tie-break
fix works end-to-end through the real Daytona snapshot pipeline, not just
in replay (T002).

The `{/app/regex.txt, /tmp/write_regex.sh}` cell only had one candidate
(step 7) in this particular run — no repeat edits to that exact file pair,
so it doesn't exercise the fix, consistent with the ticket's own
inconclusive-is-not-a-fail condition.

Next: T004 (comparative pilot) — or, given cost, consider whether T002 +
this live confirmation is sufficient evidence to skip straight to T004
rather than running more solo smoke jobs.
