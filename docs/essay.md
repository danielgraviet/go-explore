# Returning to Useful Development States

## One Sentence

Coding agents waste test-time compute by repeatedly rediscovering the same partial progress; we show that Go-Explore-style search over full sandbox snapshots lets agents reuse useful development state and solve more software tasks under the same budget.

## Abstract

Coding agents often make useful progress before they fail. They install dependencies, reproduce failures, identify relevant files, generate artifacts, start services, collect logs, and write partial fixes. Most retry systems discard this work and start the next attempt from the original repository.

We adapt the core idea of Go-Explore to software engineering: save promising states, return to them, and explore new continuations. In our setting, a state is not just a code diff or a transcript. It is a full development sandbox containing the filesystem, installed packages, build outputs, caches, logs, services, test artifacts, and the agent's trajectory context.

We evaluate whether full sandbox snapshots are better reusable search states than fresh restarts, final patches, transcripts, command replay, and git-like intermediate states. Under a fixed token and dollar budget, snapshot branching solves [X%] more Terminal-Bench tasks than independent retries and [Y%] more than best-of-N final-attempt selection. The gains are largest on tasks where setup, reproduction, or artifact generation consumes a meaningful fraction of the budget.

Our results suggest that test-time scaling for coding agents should not only sample more final answers. It should also search over reusable development states.

## Introduction

Coding agents rarely fail from a completely useless trajectory. A failed attempt may still have found the right files, installed the right dependencies, reproduced the failing test, narrowed the bug, created a partial patch, built an index, or discovered that an apparently plausible path is wrong. These intermediate states are expensive to recreate. They are also often stored outside the final code diff.

Standard retry systems mostly ignore this. They spend additional test-time compute by starting over from the original task. Best-of-N systems improve the odds by sampling many full attempts and selecting among completed patches, but they still treat intermediate progress as disposable. Memory- or transcript-based systems preserve some information, but a transcript cannot fully represent a mutated development environment. A clean checkout plus a summary does not necessarily contain installed dependencies, compiled artifacts, generated files, service state, caches, logs, or the exact local conditions under which the agent reproduced a failure.

The main idea of this paper is simple: if an agent reaches a useful development state, save it. Then fork that exact state and ask new agents to continue from it. This is the software-engineering analogue of Go-Explore's return-and-explore strategy. In Atari and robotics, the saved state might be a game screen or simulator state. For coding agents, the saved state is a full development sandbox.

This reframes coding-agent test-time scaling as a search problem over reusable states. The question is not only "how many attempts should we sample?" It is also "which intermediate states are worth returning to, and how should the remaining budget be allocated across them?"

We make two claims.

1. Full development snapshots are stronger reusable search states than compressed alternatives such as final diffs, transcripts, command logs, or replayed setup.
2. Go-Explore-style branching from selected snapshots can solve more coding tasks than scratch retries and best-of-N final-attempt selection under the same budget.

The important qualifier is "selected." Branching from arbitrary states is not enough. A useful system must identify states that are promising because they preserve progress, reduce uncertainty, or expose a new part of the search space.

## System Overview

Our system wraps a coding agent running in a Daytona sandbox. During execution, it observes command batches and terminal output. A snapshot policy converts each step into zero or more snapshot candidates. A snapshot backend freezes the live sandbox. A local archive stores metadata about the snapshot and ranks which states should be forked later.

The full loop is:

1. Run a root coding-agent attempt on a task.
2. Detect intermediate states that may be useful to revisit.
3. Save full Daytona snapshots at those states.
4. Bucket snapshots into archive cells, such as "edited these files" or "reproduced this test failure."
5. Select high-priority cells for continuation.
6. Fork child sandboxes from the selected snapshots.
7. Run continuation agents under the remaining budget.
8. Report task success, lineage, cost, repeated work, and search overhead.

The archive stores pointers and metadata, not the sandbox itself. The actual machine state lives in Daytona. The archive answers the search question: which saved state should receive more attempts?

## What Counts As A Useful State

A promising development state is one that increases the expected value of future work. It may do this by preserving setup, localizing the task, changing the repo, exposing a new failure, or avoiding a known dead end.

Candidate signals:

| Signal | Why it may matter |
| --- | --- |
| Failing test reproduced | The agent has grounded the task in an executable signal. |
| Relevant files identified | Future agents can edit sooner. |
| Dependencies installed | Setup cost has already been paid. |
| Build artifacts or indexes created | Expensive generated state is preserved. |
| Partial patch written | The repo has moved closer to a solution. |
| Test output changed | The task state has changed, even if not solved. |
| New error is more localized | The search space has narrowed. |
| Service started or configured | Runtime state may be hard to recreate exactly. |
| Failed path identified | Child agents can avoid repeating it if context transfer is correct. |

Not every snapshot is valuable. Read-only exploration, malformed patches, stale services, or a wrong answer plus overconfident context can make continuation worse than restarting. This is why the evaluation includes random-state and oracle-state controls.

## Claim 1: Full Snapshots Preserve More Useful Progress

**Claim.** Given the same downstream model, prompt, and continuation budget, a full sandbox snapshot is a better reusable state than a compressed representation of the same progress.

This claim separates state fidelity from search policy. We first ask whether returning to the exact environment helps, before asking whether our online selector chooses the right states.

### Experiment

For each task, we run a root attempt until it reaches a candidate intermediate point. From that same point, we construct multiple child-agent starting conditions.

| Condition | What the child receives |
| --- | --- |
| Fresh restart | Original task and clean initial repo. |
| Diff only | Clean repo plus current git diff. |
| Diff + transcript summary | Clean repo plus diff plus compressed parent trajectory. |
| Diff + command log | Clean repo plus diff plus exact commands and observed outputs. |
| Replayed environment | Fresh sandbox where detected setup commands are replayed. |
| Full snapshot | Forked sandbox with files, dependencies, build outputs, caches, logs, artifacts, services, and context. |

Every child receives the same continuation budget. The parent state is fixed across conditions, so differences are attributable to representation quality rather than branch-point choice.

### Metrics

| Metric | What it tests |
| --- | --- |
| Continuation solve rate | Whether the representation helps agents finish. |
| Time to reproduce failure | Whether debugging setup was preserved. |
| Time to first meaningful edit | Whether the agent avoids rediscovery. |
| Repeated setup commands | Whether work is being redone. |
| State-fidelity failures | Whether missing deps, files, caches, ports, or artifacts break continuation. |
| Context misuse failures | Whether inherited context causes the child to trust a wrong parent state. |
| Continuation diversity | Whether children explore distinct fixes rather than replaying the same path. |

### Expected Result Shape

The result supports Claim 1 if full snapshots improve solve rate and reduce repeated setup relative to all compressed conditions. It is especially convincing if replayed environments fail on tasks where hidden state matters, while snapshots continue successfully.

The result weakens Claim 1 if diff-plus-transcript or replayed setup matches full snapshots on most tasks. In that case, the extra infrastructure cost of full sandbox snapshotting may not be justified.

## Claim 2: Go-Explore Search Improves Fixed-Budget Scaling

**Claim.** Under the same total token, time, and dollar budget, Go-Explore-style snapshot branching solves more coding tasks than scratch retries and best-of-N final-attempt selection.

This claim tests the full algorithm: online snapshot capture, state selection, forked continuation, and budget allocation.

### Conditions

| Method | Budget allocation |
| --- | --- |
| Single long run | One agent receives the full budget. |
| Retry from scratch | Multiple independent agents start from the original task. |
| Best-of-N final attempts | Multiple full attempts run from scratch; a judge or verifier selects the best final patch. |
| Random snapshot branching | The system snapshots intermediate states but selects branch points randomly. |
| Promising snapshot branching | The system selects high-priority archive cells and forks continuations from them. |
| Oracle snapshot branching | Retrospective upper bound using states known to be close to success. |

The main comparison is promising snapshot branching against retry-from-scratch and best-of-N under equal budget. Random branching tests whether selection matters. Oracle branching estimates headroom.

### Fixed Budget Example

For a 100k-token budget:

| Method | Spend pattern |
| --- | --- |
| Single run | 1 agent gets 100k tokens. |
| Retry from scratch | 5 agents get 20k tokens each. |
| Best-of-N | 5 attempts get 18k tokens each; 10k tokens are reserved for judging or selection. |
| Snapshot branching | Root attempt gets 30k tokens; selected continuations share 70k tokens. |

The exact split should be swept. The paper should report sensitivity to root budget, number of snapshots, continuations per snapshot, and maximum depth.

### Metrics

| Metric | What it tests |
| --- | --- |
| Solve rate under fixed budget | Whether the method solves more tasks. |
| Unique tasks solved beyond baselines | Whether branching finds solutions scratch retries miss. |
| Cost per solved task | Whether the added infrastructure pays for itself. |
| Branch success rate | How often selected snapshots lead to success. |
| Promising-vs-random lift | Whether the selector is doing useful work. |
| Oracle gap | How much better selection could become. |
| Repeated work avoided | Whether the method reduces setup, rediscovery, and reproduction. |
| Snapshot overhead | Time and cost spent creating, restoring, and managing snapshots. |
| Continuation diversity | Whether forks explore meaningfully different fixes. |
| Regression rate from bad memory | How often inherited context makes a child worse than a restart. |

### Expected Result Shape

The strongest result is not just "snapshot branching solves more." The stronger result is:

1. Snapshot branching solves tasks missed by scratch retries.
2. It spends less budget on repeated setup and rediscovery.
3. Promising-state selection beats random-state selection.
4. Oracle selection is better still, showing room for improved selectors.
5. Snapshot overhead is small relative to saved work.

The claim is refuted if random branching matches promising branching, if scratch retries match snapshot branching under equal budget, or if snapshot overhead consumes the saved work.

## Experimental Design

We evaluate on a filtered set of Terminal-Bench tasks. The first full experiment should prioritize task diversity over repeated samples of a tiny task set. A useful initial target is 30-50 medium or medium-hard tasks with 2-3 seeds per method. Repeating 5 tasks 10 times would make the infrastructure easier to debug, but would provide weaker evidence that the method generalizes.

Task selection should avoid two failure modes:

1. Tasks that are too easy, where the root attempt already solves the task and there is no headroom.
2. Tasks that are so hard or flaky that no method gets enough signal for comparison.

The primary model should be a cost-efficient, capable coding model so the full run is affordable. The paper should describe model classes rather than depending on a quickly aging model name: for example, a strong closed model, a strong closed competitor, and an open model.

The main analysis should use confidence intervals over tasks, not just raw run counts. The unit of generalization is the task.

## Data Contract

The paper needs three levels of data.

### Task-Level Table

One row per task and method:

| Field | Meaning |
| --- | --- |
| task_id | Terminal-Bench task name. |
| difficulty | Task difficulty bucket. |
| category | Task category. |
| method | Single run, retry, best-of-N, random branch, promising branch, oracle branch. |
| solved | Whether any attempt under the method solved the task. |
| total_tokens | Sum of root, continuation, and judge tokens. |
| total_cost_usd | Dollar cost including model and sandbox costs. |
| wall_clock_seconds | End-to-end runtime. |
| n_attempts | Number of root or scratch attempts. |
| n_snapshots_created | Snapshots created during root and child runs. |
| n_snapshots_forked | Snapshots used for continuation. |

### Run-Level Table

One row per root attempt, scratch attempt, or continuation:

| Field | Meaning |
| --- | --- |
| run_id | Stable run identifier. |
| parent_run_id | Parent run, if continuation. |
| parent_snapshot | Snapshot name, if continuation. |
| method | Experimental condition. |
| task_id | Task name. |
| seed | Random seed or run index. |
| model_class | Model family bucket. |
| start_state_type | Clean, diff, transcript, replayed, full snapshot. |
| reward | Terminal-Bench reward. |
| tokens_in / tokens_out | Model usage. |
| cost_usd | Model cost. |
| duration_seconds | Runtime. |
| repeated_setup_score | Amount of setup repeated from parent or sibling attempts. |
| failure_mode | Categorized failure reason. |

### Event-Level Log

JSONL events are needed for mechanistic claims:

| Event | Required fields |
| --- | --- |
| command_executed | run_id, step_id, command, duration, exit status, output hash. |
| file_changed | run_id, step_id, path, change type, diff hash. |
| test_run | run_id, step_id, command, pass/fail counts, output hash. |
| dependency_installed | run_id, step_id, package/tool, version if available. |
| snapshot_created | run_id, step_id, snapshot_name, cell_key, score, selector reasons, overhead seconds. |
| snapshot_selected | archive_id, snapshot_name, priority, times_selected, selection policy. |
| continuation_started | child_run_id, parent_run_id, snapshot_name, context mode. |
| verifier_result | run_id, reward, verifier output hash. |

Without this data, the paper can report solve rates but cannot defend the deeper claim that the method avoids repeated work.

## Figures And Tables

The paper needs these plots:

1. Solve rate by method under fixed budget.
2. Cost per solved task by method.
3. Unique tasks solved by each method, shown as overlap or upset plot.
4. Branch success rate by snapshot event type.
5. Promising-vs-random branch lift.
6. Repeated setup commands per solved task.
7. Snapshot overhead as a fraction of total budget.
8. Oracle gap: random, heuristic, learned, and oracle selection.

The most important table is an ablation table:

| Representation | Solve rate | Time to first edit | Repeated setup | Fidelity failures |
| --- | ---: | ---: | ---: | ---: |
| Fresh restart | [ ] | [ ] | [ ] | [ ] |
| Diff only | [ ] | [ ] | [ ] | [ ] |
| Diff + transcript | [ ] | [ ] | [ ] | [ ] |
| Command replay | [ ] | [ ] | [ ] | [ ] |
| Full snapshot | [ ] | [ ] | [ ] | [ ] |

## Related Work

Go-Explore introduced the idea of solving hard exploration problems by explicitly returning to promising states and exploring from them. We use the same high-level strategy but change the definition of state. For coding agents, useful state includes the development environment, not only an observation or text context.

Existing coding-agent systems preserve progress in compressed forms. Some methods give the model localized code context and ask it to generate candidate patches. Others maintain dynamic prompts, reflections, or memory. Test-time scaling systems sample many completed trajectories and select among final patches. SWE-Search is closest in spirit because it searches over intermediate coding-agent states using a git-like tree. These systems preserve important information, but they generally do not make the full development environment the reusable unit of search.

Our work asks whether the missing environment state matters. If full snapshots only match compressed state, then simpler approaches are preferable. If full snapshots improve continuation success and reduce repeated work, then environment-level search is a useful new axis for coding-agent scaling.

Citation audit needed: verify exact claims and section references for Agentless, RepairAgent, Reflection, CodeMonkeys, SWE-Search, and Go-Explore before this becomes a paper draft.

## Threats To Validity

Snapshot branching can look artificially good if it receives more total budget than the baselines. All headline comparisons must fix total token, time, and dollar budget.

Snapshot branching can also look good if branch points are chosen retrospectively. Online promising-state selection must be the main result. Oracle selection should be labeled as an upper bound.

Continuation can fail because of bad context transfer, not because the underlying state is bad. A child that inherits a wrong answer and a prompt saying not to repeat previous work may rubber-stamp the parent. The system must measure context misuse separately from state fidelity.

Terminal-Bench tasks may underrepresent long-running development environments with services, databases, and large caches. If the benchmark mostly tests small command-line tasks, the measured benefit of full snapshots may be a lower bound for larger engineering work, but that remains a claim to test.

Daytona snapshot overhead and reliability are part of the method. Failed snapshots, slow restores, and inactive templates must be counted as costs, not hidden as infrastructure noise.

## What This Draft Forces Us To Build

To make this paper true, the system needs:

1. A persistent archive that stores snapshot names, cells, scores, parent lineage, and selection counts.
2. A selector baseline suite: list order, random, heuristic, learned or LLM-scored, and oracle.
3. Continuation modes for fresh restart, diff only, diff plus transcript, command replay, and full snapshot.
4. Budget accounting across root attempts, continuation attempts, judges, snapshot overhead, and restores.
5. Event-level logging for commands, changed files, tests, dependency installs, snapshot events, and verifier outcomes.
6. Repeated-work metrics that compare command sequences across sibling attempts.
7. Context-transfer variants so we can distinguish environment value from prompt/memory value.
8. A benchmark runner that can execute each method under a fixed budget across many tasks.
9. Analysis scripts that produce task-level, run-level, and event-level tables plus the core plots.

## Conclusion

The core result we want to earn is:

> Snapshot branching solves tasks that independent retries miss, while spending less budget repeating setup and rediscovery.

The broader point is that coding-agent progress is not only a final patch. It is a state of the development world. If test-time scaling systems can save, rank, fork, and revisit those states, they can search in a space that current retry and best-of-N systems mostly throw away.
