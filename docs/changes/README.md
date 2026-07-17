# Snapshot archive, continuation worker, cell-key fix

What this branch adds, why, and what the runs actually showed. Design rationale:
[`../snapshot-archive-proposal.md`](../snapshot-archive-proposal.md).

Tests: **91 passed, 9 skipped** (`uv run pytest -q`).

---

## 1. `go_explore/snapshots/archive.py` — new

The persistent cell → best-snapshot map.

| Symbol | What it does |
| --- | --- |
| `cell_key_for(candidate)` | Cell-key **option A**: the sorted set of files the state touched. Falls back to `<event>` when no files are known. |
| `ArchiveEntry` | One cell's best snapshot: `cell_key`, `snapshot_name`, `score`, lineage (`parent_snapshot`, `depth`), `times_selected`. |
| `SnapshotArchive` | `add` (insert or replace if better), `select(k)` (rank by score, down-weighted by `times_selected`), `mark_selected`, `promote`, `save`/`load`. |
| `ArchiveStore` | Implements the existing `SnapshotStore` protocol, so `AsyncSnapshotManager` needs **no change** — it just gets handed a different store. Persists after every accepted snapshot. |

**Why it exists:** four gaps traced to one missing structure — records died in
`InMemorySnapshotStore`, continuation forked in list order,
`HeuristicSnapshotSelector` was never called, and local↔remote was linked only by
a naming convention.

**Design note:** the archive stores **pointers, not state**. All cells of a real
run fit in ~1.2 KB; the machine state stays in Daytona. That boundary is why the
store swap was a one-line change.

## 2. `go_explore/agents/snapshot_agent.py`

Hands the manager an `ArchiveStore` instead of the default in-memory one. Harbor
passes `logs_dir` = `jobs/<job>/<trial>/agent`, so the archive lands at
`logs_dir.parent.parent` = **`jobs/<job>/archive.json`**, the job root.

## 3. `go_explore/cli.py`

Adds `--from-archive` / `--archive-path` to `continue-from-snapshots`. The worker
loads `archive.json`, calls `select(k)`, forks **by score** rather than list
order, prints what it picked, then `mark_selected()`s those cells and saves — so
a later run rotates onward through the frontier instead of re-picking the same
winners.

**Observed:** on `fix-git`, list-order forks `step-0`, which the archive scores
**0.00 — the worst cell**. The archive forks `step-2` at **3.00**. Same run,
better pick, purely from ranking.

## 4. `go_explore/snapshots/policies.py` — the cell-key bug fix

`_changed_files_from_commands` only parsed `cat >` and `git add`, but
`_looks_like_file_edit` also recognises `sed -i`, `tee`, `apply_patch`. So a
`sed -i` step was tagged a **file edit with zero files**, fell back to the
`<file_edit>` event bucket, and collapsed unrelated states together.

**Observed damage** (`sanitize-git-repo`): 10 snapshots → **2 cells**, every one
an event fallback. Six `sed` edits, each sanitizing a *different secret in a
different file*, became one cell. **8 of 10 snapshots discarded before selection
ever ran.**

Added `_edit_targets` (parses `sed -i` operands, skipping flags and the script;
handles `-i.bak`, `-e`/`-f`, multiple files, `tee`) and `_normalize_path` (so
`./a/b.py` and `a/b.py` are the same cell).

**Before / after**, replaying the same saved trajectory:

```
BEFORE:  3 cells, all event fallbacks
  <file_edit>   ← steps [11,12,13,14,15,16]    6 states → 1 kept, 5 discarded

AFTER:   4 cells, 2 file-based
  {ray_processing/process.py}        ← steps [11,12]
  {ray_processing/ray_cluster.yaml}  ← steps [13,14,15,16]
```

(6 edits → 2 cells is *correct*: four touched the same file, and under option A
same-file edits are the same cell.)

Confirmed live on `chess-best-move`, which produced a real file-based cell —
`{/app/move.txt}`, score 1.25 — where before it would have been `<file_edit>`.

**Known boundary:** `apply_patch` and `python - <<HEREDOC` are still
unextractable (their targets live inside a patch body or script), so those steps
keep falling back to `<file_edit>`. Documented in the docstring and pinned by a
test so the limit is explicit rather than implied.

## 5. Tests

- `tests/test_archive.py` (13 tests): cell keying, one-entry-per-cell,
  keep-the-better-snapshot, `select` ordering + `k`, `mark_selected` rotating the
  frontier, `promote` lineage, save/load round-trip, `ArchiveStore` satisfying the
  store protocol.
- `tests/test_changed_files.py` (12 tests): regression cover using the **exact
  `sed` command from the observed run**, plus a test pinning the known-
  unextractable forms.
- `tests/test_snapshot_agent_integration.py`: one assertion updated — the agent's
  store is now `ArchiveStore`. Intentional behaviour change.

## 6. `experiments/`

- `run_comparison.sh TASK N [MODEL]` — both arms at equal budget: baseline = N
  independent attempts; continuation = 1 root + N-1 forks of its snapshots.
- `summarize_comparison.py` — parses both arms into a table + verdict, writes a
  memo to `docs/experiments/`. Verdicts include *"no signal — the baseline already
  solves it every time"*, so a wasted run reports itself.

---

## What the runs showed

**Verified on real Daytona runs:**
- Full loop: explore → snapshot → archive → score → select → fork → resume.
  `fix-git`: root 1.0, continuation from `step-2` → 1.0.
- Archive persists through a live run and dedups (4 snapshots → 3 cells).
- Archive selection beats list order (3.00 cell vs 0.00 cell).
- Opening a snapshot shows the **whole frozen machine** — a real unresolved merge
  conflict, git index mid-merge, plus `/tmp/go_explore_context.md`.

**The hypothesis is still not established.** Continuation has not beaten
independent attempts on any task tried:

| Task | Root | Forks | Note |
| --- | --- | --- | --- |
| `fix-git` | 1.0 | 1.0 | too easy — no room to show benefit |
| `sanitize-git-repo` | 0.0 | 0.0, 0.0 | ran with the cell-key bug live; selection was crippled |
| `chess-best-move` | 0.0 | 0.0, 0.0 | fix live, real cells — see below |

### Why `chess-best-move` failed, mechanically

The root wrote a **wrong** answer (`c8e8`) to `/app/move.txt` and scored 0.0. We
forked the state right after that write. The child ran **3 steps** against the
root's 24: it `cat`-ed the file, said *"The task has been completed
successfully… based on the extensive analysis done in the previous attempt"*, and
called `mark_task_complete`.

It inherited a failure, was told *"here's what was tried, so you don't repeat
it"*, trusted it, and quit. Three causes compound:

1. **The context carries no failure signal** — `/tmp/go_explore_context.md` says
   what the parent *tried*, never that it *failed* (gap #1 below).
2. **The preamble discourages redoing work** — exactly wrong when the prior
   attempt was wrong.
3. **A snapshot of a wrong answer looks like progress** — nothing distinguishes
   "done" from "done wrong".

**Implication:** continuation as currently designed can be *worse* than
restarting — an independent attempt would at least try. Fixing the context to
carry the verifier signal should come before any further comparison; the current
results measure a broken memory-transfer, not the Go-Explore idea.

## Known gaps (not addressed here)

1. **`reward_signal` is `null` on every entry.** `tests_passed` is never
   populated, so the selector's strongest intended term is dead and scoring runs
   on event heuristics alone. Caused an observed misranking: on `fix-git`, git
   printing *"Automatic merge failed"* matched `"failed" in observation` → the
   merge scored a `test_run` (+3.0) and outranked the step that actually fixed the
   task (1.25).
2. **Lineage is never written back.** Forked children write archives claiming
   `depth=0, parent=None`; `promote()` exists but nothing calls it across jobs, so
   the tree lives only in `continuation-report.json`. Archives are per-job and
   disconnected.
3. **The archive keeps no record of what it discards** — which cell each dropped
   snapshot belonged to is unrecoverable.
4. **No timeout in the continuation runner.** `run_continuation_plan` calls
   `subprocess.run` with no `timeout=`; one hung fork stalled the whole plan for 30
   minutes and took the report with it (a completed fork's result was lost). It
   also leaked a live Daytona sandbox.
5. **No eviction.** Snapshots accumulate and quotas are small and vary by account
   — we hit **100/100** on one and **30/30** on another, where a single
   `sanitize-git-repo` run burns 10. At any real branching factor this is a hard
   blocker, not a nice-to-have.
6. **Harbor version is unpinned.** The repo pins `daytona` but not `harbor`; the
   agent import-path contract changed between `0.1.44` (works) and `0.18`
   (factory function rejected — "must be a class"), so a fresh install breaks.
