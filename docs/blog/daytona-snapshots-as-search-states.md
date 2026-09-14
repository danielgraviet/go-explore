# Snapshots as search states: what we learned running Go-Explore over Daytona sandboxes

*Intern technical draft. Every numerical claim is tied to
[docs/claim-ledger.md](../claim-ledger.md). Do not edit numbers without
updating the ledger.*

Coding agents pay for installs, builds, and reproductions, then throw the
machine away. The default test-time strategy is retry-from-scratch: sample
another full attempt from the original repo.

We asked whether a Daytona snapshot could be more than an environment
template. Could it be a **search node** — a frozen mid-task machine that a
new agent forks into, the way Go-Explore returns to a promising Atari
state before exploring from it?
#note: this should include the motivation for our question. If we can solve
more with a fixed token budget, and use snapshots efficevtly, we are more token efficient,
have more diverse answers, and solve more tasks. just like go-explore original paper. 

The infrastructure answer is yes. The algorithm answer, under a matched
token budget on **file-centric** Terminal-Bench tasks, is not yet.
A patch is often enough there. The interesting Daytona question is when
progress lives in the machine instead.

## The idea

Go-Explore's rule is simple: remember promising states, return to them
without noise, then explore. In Atari the state is a simulator snapshot.
For a coding agent the analogous state is the whole development sandbox:
filesystem, packages, build outputs, git index, logs, maybe a running
service.

Daytona already uses snapshots as reusable starting images. This project
uses them as **intermediate search states**. During a Harbor Terminus-2
run we snapshot after interesting agent steps, store metadata in a local
archive, pick a cell, and launch a child job with
`snapshot_template_name=<snapshot>`.

```text
Terminus-2
  -> hook async _execute_commands()
  -> snapshot policy (file edit, test, discovery, ...)
  -> Daytona create_snapshot
  -> archive cell + score
  -> select_k
  -> child Harbor job restored from that snapshot
```

The archive stores pointers and scores. The machine lives in Daytona.

## The system

A wrapper around Harbor's async Terminus-2 agent sees each command batch
and terminal observation. A policy decides whether the step is a
snapshot candidate. A Daytona backend freezes the live sandbox as
`go-explore-<trial>-step-N`. After the root job finishes, a continuation
runner reads `archive.json`, ranks cells, and starts child Harbor jobs
from the selected restore references. To accomplish a seamless integration into
Harbor we had to import a new snapshot compatible agent, and then pin specific versions
of Daytaon and Harbor to expose the live snapshot/fork on an async sandbox.

## Restore works

On four easy Terminal-Bench anchors (`kv-store-grpc`, `pypi-server`,
`nginx-request-logging`, `log-summary-date-ranges`), we ran a restore
reliability check, not a "branching wins" check. Every planned
continuation that ran restored from a recorded Daytona snapshot: **24/24**.
Solve rates were statistically indistinguishable from clean attempts
(continuations 21/24, retries 31/36, Fisher's exact p = 1.0). That is
the expected result on ceiling tasks.

The qualitative demo is `fix-git`. Forking a snapshot brought back the
whole frozen machine, including an unresolved merge conflict and a git
index sitting mid-merge. That state is not a diff and not a transcript.

## It does not beat retry

The pre-registered headline comparison used five screened tasks, five
seeds, a 1,000,000-token cap, and the same model
(`claude-haiku-4-5`) #lets not name the model, it should be a category like "lighter model". Retry was three independent attempts sharing the
budget. Promising-branch was one root plus up to two snapshot-restored
children sharing the same budget.


| Task                     | Retry (any of 3) | Branch (root or child) |
| ------------------------ | ---------------- | ---------------------- |
| git-multibranch          | 5/5              | 1/5                    |
| extract-elf              | 4/5              | 3/5                    |
| custom-memory-heap-crash | 3/5              | 1/5                    |
| code-from-image          | 3/5              | 1/5                    |
| large-scale-text-editing | 2/5              | 0/5                    |
| **Total**                | **17/25 (68%)**  | **6/25 (24%)**         |

![Headline solve rates: retry 17/25 versus snapshot branching 6/25.](../whitepaper/figures/fig3-headline-solve-rates.svg)


Retry won on every task. That is the headline result, not a bug we
folded away.

The rescue mechanism still fired. Four documented cases of a failed root
being solved by a child on a later budget share:

- `extract-elf` seeds 1, 2, 3
- `custom-memory-heap-crash` seed 3

The mechanism is real. It is not frequent enough, at this split, to beat
three independent retries.

## Four reasons restore loses

![Four failure modes: budget split, sticky wrong state, handoff cost, weak selection.](../whitepaper/figures/fig6-failure-modes.svg)

These are the failure modes we actually saw. Details and coding rules
are in [docs/failure-taxonomy.md](../failure-taxonomy.md).

**Budget split.** Most failures on both methods were
`AgentBudgetExhaustedError`, even after raising the cap to 1e6. Splitting
a tight budget into a starved root and starved children is not the same
as giving three agents a full independent draw. Cutting the root's share
from 0.3 to 0.15 did not help: a thinner root produces a thinner archive.

**Wrong-state basins.** Restore is faithful, including when the parent
wrote a bad answer. On `regex-log`, children restored an early
`/app/regex.txt` and failed the hidden verifier. Removing parent prompt
context cut tokens from 127k to 5k and still failed from the same
snapshot. The inherited file was the trap, not the summary.

**Verification archaeology.** A restored sandbox does not restore the
child's trust. We watched children spend turns discovering that `python`
was not on PATH, that `pytest` was missing, and that the real check lives
at `/tests/test.sh`. On one trajectory the winning retry finished in 11
steps / 90k tokens; a child on the same task took 26 steps / 190k, mostly
before any new debugging.

**False confidence.** Early on, a `chess-best-move` child restored a
wrong `/app/move.txt`, read it, declared the task complete "based on the
extensive analysis in the previous attempt," and quit in three steps. The
parent had failed with no signal that it had failed, plus a prompt
telling the child not to repeat prior work. Later, archive scoring
treated a bare "I'm done" as a verifier event, so we preferentially
forked the states that had lied.

## When it helped

Two narrower results are worth keeping separate from the 17/25 number.

On `extract-elf`, every completed seed whose root died on budget
exhaustion had `snapshot-0` go on to solve. That is the Go-Explore
picture: return to a saved machine, spend the remaining budget there.

After we stopped the archive from freezing on the *first* edit to a
file (tied scores used to keep the incumbent), `regex-log` produced 2/8
root-fail → child-solve chains while matched retry was 0/8. The same
pilot also showed the inverse: seeds where the root already solved, the
child launched anyway, and the chain looked worse. Selection and "don't
continue past a solved root" matter as much as the snapshot API.

Do not average these pilots with the headline table. Different budget,
context mode, and protocol.

## File-centric vs machine state (Aug 15)

Terminal-Bench was the right validity move and a weak product demo.
Most TB progress is files. We ran a matched-cap representation ablation
(clean / git diff / diff+transcript / command replay / full snapshot,
200k remaining tokens, Haiku 4.5) on `extract-elf` and `regex-log`.

On the four `extract-elf` seeds whose diffs applied, **a compressed start
state solved and the full snapshot did not** (diff on seeds 1, 3, 4;
command replay on seed 2). That is ledger S19. It is the opposite of
“you always need a VM snapshot.” When the useful state is a file, Daytona
restore is optional.

`regex-log` d**iffs were execut**or failures (`git apply` on a bad
`parent.diff`) on all five seeds; those arms are invalid. Snapshot restore
did solve extract-elf seed 0 and regex-log seed 0. n is small; do not
upgrade S19 into “snapshots never help.”

A separate recovery replication (8 seeds, skip children if the root
already solved) is ledger S20: extract-elf **rescued 4/6 failed roots**,
regex-log **1/8**. Matched retry was 3/8 on both. Skip-if-root-solved
fired on extract-elf seeds 0 and 4. Do not pool S20 with 17/25.

The Daytona-shaped follow-up is a task where a git apply of the
checkpoint is *not* the checkpoint. On `staged-service-repair` (hidden
lot code only in `/var/lib/inventory/store.db`), the same planted
checkpoint and 200k remaining cap gave:


| Seed | clean | diff_only | full_snapshot |
| ---- | ----- | --------- | ------------- |
| 0    | 0.0   | 0.0       | **1.0**       |
| 1    | 0.0   | 0.0       | 0.0           |
| 2    | 0.0   | 0.0       | **1.0**       |
| 3    | 0.0   | budget    | **1.0**       |
| 4    | 0.0   | 0.0       | **1.0**       |

![Warehouse representation: snapshot 4/5, git diff 0/5, clean 0/5.](../whitepaper/figures/fig4-warehouse-arms.svg)

![Token use on the same fifteen runs. Snapshot solves used 21k–41k tokens.](../whitepaper/figures/fig5-warehouse-tokens.svg)


Snapshot **4/5**, `diff_only` **0/5**, `clean` **0/5**. Ledger S21.
Inclusion held: the lot is not in `parent.diff` (the patch is empty;
progress was the warehouse DB). Restore overhead ~2.8–3.5s. Seed 1
restored the DB but did not apply the remaining migration. Do not pool
with 17/25.

The comparison that matters is snapshot versus a start that does **not**
already have the warehouse. Clean retry never sees the lot. A git patch
of the checkpoint is empty. Only the restore keeps the sticky note.

Protocol:
[docs/experiments/env-progress-ablation.md](../experiments/env-progress-ablation.md).
Memo:
[docs/experiments/env-progress-ablation-results.md](../experiments/env-progress-ablation-results.md).

## What this means if you use Daytona snapshots

Snapshots are a search primitive, not only an image cache. You can freeze
a live coding sandbox and boot another agent into it. We did that
end-to-end through Harbor on Terminal-Bench.

On file-centric tasks, expect diffs and retries to look strong. Use a
full snapshot when the child would otherwise reinstall, reseed, or lose
process/DB/index state that is not in git. Experiment E is the case
where that last clause is the whole task.

The hard problems are not "can Daytona restore." They are:

1. **Grounded scoring.** Rank states by executed checks, not by the
  agent's narration.
2. **Handoff.** A new agent in an old machine still has to re-establish
  how to verify, and will trust inherited files.
3. **Budget shape.** Independent retries keep optionality. Splitting one
  budget across a lineage spends optionality on a possibly-wrong basin.

If you are using snapshots as identical eval templates, none of this
hurts you. If you want them as agent search nodes, plan for selection
and handoff, not only for fork latency.

## Try it

```bash
uv tool install "harbor==0.1.44" --with "daytona>=0.194.0"
set -a; source .env; set +a
export PYTHONPATH="$PWD"

harbor run --env daytona --jobs-dir jobs --n-attempts 1 --n-concurrent 1 \
  --dataset terminal-bench@2.0 --include-task-name fix-git \
  --model anthropic/claude-haiku-4-5-20251001 \
  --job-name snapshot-demo --export-traces \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2

uv run python -m go_explore.cli continue-from-snapshots jobs/snapshot-demo \
  --from-archive --max-snapshots 1 --job-prefix snapshot-demo-cont --execute
```

Omit `--agent terminus-2`. The import path is the agent.

A diagnostic that compares a restored child with a clean retry at the
same remaining token cap (not a headline solve-rate table):

```bash
uv run python -m go_explore.cli checkpoint-diagnostic \
  jobs/<root-job> \
  --snapshot-name <exact-daytona-snapshot-name> \
  --remaining-token-budget 200000 \
  --child-job-name <root-job>-diagnostic-child \
  --clean-job-name <root-job>-diagnostic-clean \
  --context-mode preflight_verification
```

The research repo is this project. The frozen headline numbers and the
list of claims we will not make live in `docs/claim-ledger.md`.