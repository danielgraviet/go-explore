# T001 — Fix archive cell-key granularity

## Problem
`cell_key_for` (`go_explore/snapshots/archive.py:30`) buckets snapshots only
by which files changed. `SnapshotArchive.add` only replaces a cell's stored
entry when the new score is strictly greater (`archive.py:138`,
`incumbent.score >= score` rejects ties). `HeuristicSnapshotSelector.score`
gives a flat `+1.0` for any `file_edit` regardless of content.

Verified in `jobs/phase6-viability-pilot-regex-log-promising-branch-none-promising-branch-seed-0-root`:
the agent edited `/app/regex.txt` at steps 0, 3, 5, 7. Only step 0 was
accepted (`archive_accepted: true`); 3/5/7 were rejected
(`archive_accepted: false`, see `events.jsonl`) because they scored no
higher than the incumbent. The archive permanently froze on the agent's
first, least-refined attempt. This is why the "promising" branch child
restored a near-start state and performed no better than a cold retry — it
never had access to the agent's later, more-refined edits.

Already flagged as a known gap in code: `archive.py:36`, "Upgrade path is
option B (files + tests passing) once a mid-run test signal exists" — never
implemented.

## Fix
Make the cell key or acceptance rule sensitive to progress within a file
set, not just file identity, so a later/better edit can displace an earlier
one. Two independent levers, pick the smaller one first:

1. **Tie-break toward recency**: change `incumbent.score >= score` to
   `incumbent.score > score` so equal-scoring later edits replace earlier
   ones (cheap, one-line, no schema change).
2. **Progress-sensitive scoring**: when the score is otherwise flat
   (repeated `file_edit` to the same cell), weight by count of prior edits
   to that same file set or by presence of a partial test/lint signal, so
   later revisions score higher rather than tying.

Do not change `cell_key_for` itself yet (splitting cells by revision count
would just recreate the "each edit is a unique cell" problem the design
doc already rejected — collapsing similar states is the point). Prefer
fixing acceptance/scoring over widening the key.

## Files
- `go_explore/snapshots/archive.py` (`SnapshotArchive.add`, line ~138)
- `go_explore/snapshots/policies.py` (`HeuristicSnapshotSelector.score`, line ~110)

## Verification
- Add/extend a unit test in the existing snapshot archive test suite
  (find via `grep -rl cell_key_for tests/`) asserting: given two
  `file_edit` candidates for the same file, the later one replaces the
  earlier one in the archive.
- `.venv/bin/python -m pytest -v -k archive` (or the relevant test file)
  must pass.

## Status
Lever 1 (tie-break toward recency) implemented: `archive.py:138` changed
`incumbent.score >= score` to `incumbent.score > score`, with a comment
explaining why. Regression test added:
`test_add_replaces_a_tied_incumbent_with_the_later_candidate` in
`tests/test_archive.py`. Full suite passes (197 passed, 9 skipped).

Confirmed against the real regex-log root data
(`jobs/phase6-viability-pilot-regex-log-promising-branch-none-.../events.jsonl`):
steps 3/5/7 scored exactly 1.25, tied with step 0's 1.25 — this was a pure
tie, not a case needing progress-sensitive scoring. Lever 1 alone resolves
this specific case, so lever 2 (progress-sensitive scoring) is not
implemented — defer unless T002/T003 replay shows ties aren't the whole
story elsewhere.

Next: T002 (replay-verify against the same job's trajectory).
