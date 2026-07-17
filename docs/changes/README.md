# Change log: snapshot archive, continuation worker, cell-key fix

Everything added in this pass, why, and what it's grounded in. Full diff:
[`archive-work.diff`](archive-work.diff). Design rationale:
[`../snapshot-archive-proposal.md`](../snapshot-archive-proposal.md).

Tests: **90 passed, 9 skipped** (`uv run pytest -q`).

---

## 1. `go_explore/snapshots/archive.py` — new, 227 lines

The persistent cell → best-snapshot map. Two classes:

| Symbol | What it does |
| --- | --- |
| `cell_key_for(candidate)` | Cell-key **option A**: the sorted set of files the state touched. Falls back to `<event>` when no files are known. |
| `ArchiveEntry` | One cell's best snapshot: `cell_key`, `snapshot_name`, `score`, lineage (`parent_snapshot`, `depth`), `times_selected`. |
| `SnapshotArchive` | `add` (insert or replace if better), `select(k)` (rank by score, down-weighted by `times_selected`), `mark_selected`, `promote`, `save`/`load`. |
| `ArchiveStore` | Implements the existing `SnapshotStore` protocol, so `AsyncSnapshotManager` needs **no change** — it just gets handed a different store. Persists after every accepted snapshot. |

**Why it exists:** four separate gaps traced to one missing structure — records
died in `InMemorySnapshotStore`, continuation forked in list order,
`HeuristicSnapshotSelector` was never called, and local↔remote was linked only by
a naming convention.

**Design note:** the archive stores **pointers, not state**. All three cells of a
real run fit in 1.2 KB; the machine state stays in Daytona. That boundary is why
the store swap was a one-line change.

## 2. `go_explore/agents/snapshot_agent.py` — +8 lines

Hands the manager an `ArchiveStore` instead of the default in-memory one, and
adds `_archive_path()`. Harbor passes `logs_dir` = `jobs/<job>/<trial>/agent`, so
the archive lands at `logs_dir.parent.parent` = **`jobs/<job>/archive.json`** —
the job root, per the proposal.

## 3. `go_explore/cli.py` — +26 lines

Adds `--from-archive` and `--archive-path` to `continue-from-snapshots`. With the
flag, the continuation worker loads `archive.json`, calls `select(k)`, and forks
**by score** instead of by list order — printing which cells it picked and why.

**Why it matters (observed):** on the `fix-git` run, list-order forks `step-0`,
which the archive scores **0.00 — the worst cell**. The archive forks `step-2`
at **3.00**. Same run, better pick, purely from ranking.

## 4. `go_explore/snapshots/policies.py` — +60 lines · the bug fix

`_changed_files_from_commands` only parsed `cat >` and `git add`, but
`_looks_like_file_edit` also recognises `sed -i`, `tee`, `apply_patch`. So a
`sed -i` step was tagged a **file edit with zero files** — and since the cell key
buckets by changed files, it silently fell back to `<file_edit>` and collapsed
unrelated states together.

**Observed damage** (`sanitize-git-repo`): 10 snapshots → **2 cells**, every one
an event fallback. Six `sed` edits, each sanitizing a *different secret in a
different file*, all became one cell — the archive discarded five of them, plus
three more. **8 of 10 snapshots thrown away before selection ever ran.**

Added `_edit_targets` (parses `sed -i` operands, skipping flags and the script
expression; handles `-i.bak`, `-e`/`-f`, multiple files, `tee`) and
`_normalize_path` (so `./a/b.py` and `a/b.py` are the same cell).

**Before / after**, replaying the same saved trajectory:

```
BEFORE:  3 cells, all fallbacks
  <file_edit>   ← steps [11,12,13,14,15,16]    6 states → 1 kept, 5 discarded

AFTER:   4 cells, 2 file-based
  {ray_processing/process.py}        ← steps [11,12]
  {ray_processing/ray_cluster.yaml}  ← steps [13,14,15,16]
```

(6 edits → 2 cells is *correct*: four touched the same file, and under option A
same-file edits are the same cell.)

The docstring now states the invariant explicitly: **any edit form recognized by
`_looks_like_file_edit` must have its target extractable here.**

## 5. Tests — new

- `tests/test_archive.py` (151 lines, 13 tests): cell keying, one-entry-per-cell,
  keep-the-better-snapshot, `select` ordering + `k`, `mark_selected` rotating the
  frontier, `promote` lineage, save/load round-trip, and `ArchiveStore` satisfying
  the store protocol.
- `tests/test_changed_files.py` (85 lines, 11 tests): regression cover for the
  bug, using the **exact `sed` command from the observed run**. The last test
  guards the detection/extraction invariant so this can't regress.
- `tests/test_snapshot_agent_integration.py`: one assertion updated —
  the agent's store is now `ArchiveStore`, not `InMemorySnapshotStore`. Intentional
  behaviour change, not a fix-up.

## 6. `experiments/` — new

- `run_comparison.sh TASK N [MODEL]` — runs both arms at equal budget: baseline =
  N independent attempts; continuation = 1 root + N-1 forks of its snapshots.
- `summarize_comparison.py` — parses both arms into a table + verdict, writes a
  memo to `docs/experiments/`. Verdicts include *"no signal — the baseline already
  solves it every time"*, so a wasted run reports itself.

---

## What's verified vs. what isn't

**Verified on real runs:**
- Full loop end-to-end on Daytona: explore → snapshot → archive → score → select →
  fork → resume. `fix-git`: root 1.0, continuation from `step-2` → 1.0.
- Archive persists through a live run; dedups (4 snapshots → 3 cells).
- Archive selection beats list order (3.00 cell vs 0.00 cell).
- Opening a snapshot shows the **whole frozen machine** — a real unresolved merge
  conflict, git index mid-merge, plus `/tmp/go_explore_context.md`.

**Not established:**
- **That continuations beat independent attempts.** `fix-git` is too easy (both
  arms 1.0). On `sanitize-git-repo` Haiku failed from scratch *and* from both
  forks — but that test ran with the cell-key bug live, so selection was crippled
  before the fork. **The hypothesis remains untested.** Re-running the comparison
  with the fix is the next step.

## Known gaps (not addressed here)

1. **`reward_signal` is `null` on every entry.** `tests_passed` is never
   populated, so the selector's strongest intended term is dead and scoring runs
   on event heuristics alone. Directly caused an observed misranking: on `fix-git`,
   git printing *"Automatic merge failed"* matched `"failed" in observation` → the
   merge was scored a `test_run` (+3.0) and outranked the step that actually fixed
   the task (1.25).
2. **Lineage is never written back.** Forked children write archives claiming
   `depth=0, parent=None`; `promote()` exists but nothing calls it across jobs, so
   the tree lives only in `continuation-report.json`. Archives are per-job and
   disconnected.
3. **The archive keeps no record of what it discards** — which cell each dropped
   snapshot belonged to is unrecoverable.
4. **No timeout in the continuation runner.** `run_continuation_plan` calls
   `subprocess.run` with no `timeout=`; one hung fork hung the whole plan for 30
   minutes and took the report with it (a completed fork's result was lost). It
   also leaked a live Daytona sandbox.
5. **No eviction.** 30 `go-explore-*` snapshots accumulated against a **100
   quota** we already hit once on another account.
6. **Harbor version is unpinned.** The repo pins `daytona` but not `harbor`; the
   agent import-path contract changed between `0.1.44` (what works) and `0.18`
   (factory function rejected — "must be a class"), so a fresh install breaks.
