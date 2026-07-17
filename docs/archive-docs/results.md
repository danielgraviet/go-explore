# The Archive: results & how to reproduce

All numbers below are from real Haiku 4.5 runs on Daytona. Nothing is mocked.

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

Requires **harbor==0.1.44** with the `daytona>=0.194` extra:

```bash
uv tool install "harbor==0.1.44" --with "daytona>=0.194.0"
```

## What works

The full loop runs end to end. On `fix-git`, root scores 1.0, we snapshot → fork `step-2`, the child also scores 1.0. Snapshots persist and dedup: 4 snapshots collapse to 3 cells and get written to `archive.json`. Ranking beats list order: the archive forks `step-2` (score 3.0), whereas naive list order would fork `step-0` (score 0.0). And the fork is real: booting a snapshot brings back the whole frozen machine, down to an unresolved merge conflict and a git index sitting midmerge.

Example `archive.json` (fix-git):

```
cell_key             snapshot  event      score
<test_run>           step-2    test_run   3.00   ★ forked
{_includes/about.md} step-4    file_edit  1.25
<command>            step-0    command    0.00   (list order would pick this)
```

## What isn't shown yet: that it helps

Continuation has not beaten independent attempts on any task we've tried.

| Task | Root | Forks | Why |
| --- | --- | --- | --- |
| `fix-git` | 1.0 | 1.0 | too easy, no headroom |
| `sanitize-git-repo` | 0.0 | 0.0, 0.0 | ran with the cellkey bug; selection was crippled |
| `chess-best-move` | 0.0 | 0.0, 0.0 | fix live, real cells, failed for the reason below |

### Why chess failed (think is interesting)

The root wrote a wrong answer to `/app/move.txt` (score 0.0), and we forked that state. The child ran 3 steps versus the root's 24: it read the file, declared the task complete "based on the extensive analysis in the previous attempt," and quit.

It got a failure with no signal that it was a failure, plus a prompt telling it not to repeat prior work. So it rubber-stamped the wrong answer.

The takeaway: continuation as currently built can be worse than restarting, a fresh attempt would at least try. These negative results are measuring broken memory transfer, not the idea itself.
