# The archive: results & how to reproduce

All numbers are from real Haiku 4.5 runs on Daytona. Nothing mocked.

## Reproduce

```bash
# 1. run the agent — writes jobs/<job>/archive.json
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"; export PYTHONPATH="$PWD"
harbor run --env daytona --jobs-dir jobs --n-attempts 1 --n-concurrent 1 \
  --dataset terminal-bench@2.0 --task-name fix-git --n-tasks 1 \
  --model anthropic/claude-haiku-4-5-20251001 --job-name my-run --export-traces \
  --agent-import-path go_explore.agents.factory:snapshot_aware_terminus2_factory

# 2. see what it captured
cat jobs/my-run/archive.json

# 3. fork the best-scoring cell
uv run python3 -m go_explore.cli continue-from-snapshots jobs/my-run \
  --from-archive --max-snapshots 1 --job-prefix my-cont --execute
```

Requires **harbor==0.1.44** with the `daytona>=0.194` extra
(`uv tool install "harbor==0.1.44" --with "daytona>=0.194.0"`).

## What works

| | Evidence |
| --- | --- |
| Full loop | `fix-git`: root 1.0 → snapshot → fork `step-2` → 1.0 |
| Persist + dedup | 4 snapshots → 3 cells, written to `archive.json` |
| Rank beats list order | archive forks `step-2` (3.0); list order forks `step-0` (0.0) |
| Real fork | booting a snapshot shows the whole frozen machine — unresolved merge conflict, git index mid-merge |

Example `archive.json` (fix-git):

```
cell_key             snapshot  event      score
<test_run>           step-2    test_run   3.00   ★ forked
{_includes/about.md} step-4    file_edit  1.25
<command>            step-0    command    0.00   (list order would pick this)
```

## What isn't shown: that it *helps*

Continuation has not beaten independent attempts on any task tried.

| Task | Root | Forks | Why |
| --- | --- | --- | --- |
| `fix-git` | 1.0 | 1.0 | too easy — no room |
| `sanitize-git-repo` | 0.0 | 0.0, 0.0 | ran with the cell-key bug; selection crippled |
| `chess-best-move` | 0.0 | 0.0, 0.0 | fix live, real cells — failed for the reason below |

### Why chess failed (the useful finding)

Root wrote a **wrong** answer to `/app/move.txt` (0.0). We forked that state. The
child ran **3 steps** vs the root's 24: it read the file, said *"the task has been
completed successfully… based on the extensive analysis in the previous attempt,"*
and quit.

It inherited a failure with **no signal that it failed**, plus a prompt saying
"don't repeat prior work." So it rubber-stamped the wrong answer.
**Continuation as built can be worse than restarting** — a fresh attempt would at
least try. The negative results measure broken memory-transfer, not the idea.

## Gaps (fix in this order)

1. **`reward_signal` is always `null`** — no mid-run test signal, so scoring runs
   on rough heuristics. Root cause of the chess failure and of a `fix-git`
   misrank (git's *"Automatic merge failed"* scored as a test). **Fix first.**
2. **Lineage not written back** — children record `depth=0, parent=None`;
   `promote()` isn't wired across jobs, so the tree only lives in
   `continuation-report.json`.
3. **No timeout in the continuation runner** — one hung fork stalled everything
   30 min and leaked a sandbox.
4. **No eviction** — quotas are small (hit 30/30 and 100/100); one run burns ~10.
5. **Harbor unpinned** — fresh installs grab 0.18 and break.
