# Returning to development states: when full sandbox snapshots help coding agents, and when they do not

Technical report / workshop draft. Frozen headline numbers are never revised. Evidence map: [docs/claim-ledger.md](../claim-ledger.md). Citation-safe related work: [docs/related-work-citation-audit.md](../related-work-citation-audit.md). Original (unsupported) hypothesis: [docs/archive-docs/essay-original-hypothesis.md](../archive-docs/essay-original-hypothesis.md).

## Abstract

Coding agents often make useful progress before they fail, but retry-from-scratch discards the machine state created along the way. This makes failure recovery an interesting search problem. If intermediate environment states preserve meaningful progress, restoring and branching from them could outperform repeatedly restarting from the initial state. We implement Go-Explore-style search over full Daytona sandbox snapshots and find that on a pre-registered harder Terminal-Bench subset independent retries outperform snapshot-based search under a matched token budget (17/25 versus 6/25). The same remaining-budget comparison on a custom task whose required state lives in a SQLite database outside the repository goes the other way: full snapshots solve 4/5 attempts, while a git diff of the same checkpoint and a clean restart solve 0/5. Our results suggest that environment-level search is most valuable when useful progress lives outside easily reconstructed source state, motivating snapshot-aware agents that preserve and revisit high-value execution states during long-horizon coding tasks.

## 1. Introduction

A coding-agent failure is rarely a clean reset point. Consider an agent debugging a repository: it installs missing dependencies, reproduces the failing test, modifies several files, and creates a local database needed by the application. It then makes one bad edit and fails the task. A standard retry starts again from the original repository, discarding not only the bad edit but also every useful change to the machine that came before it.

Most test-time scaling methods operate above this machine state. Independent retries sample new trajectories from the initial environment; memory systems preserve text; and search methods such as SWE-Search preserve source-level state such as commits and file context. None of these necessarily preserve the complete execution environment: installed packages, running services, generated artifacts, databases, caches, and other state accumulated during interaction.

Go-Explore (Ecoffet et al., 2021) offers a natural alternative: remember promising states, return to them, and explore again. We apply this idea to coding agents by treating a full Daytona sandbox snapshot as the searchable state. A snapshot freezes the live machine so that a new agent can resume from an intermediate point rather than reconstructing it from the repository or a textual summary.

We initially hypothesized that branching from promising snapshots would solve more tasks than independent retry under a fixed token budget. Our experiments refute that broad hypothesis on the Terminal-Bench tasks we tested, but they also reveal when environment-level state matters and what prevents snapshot search from being effective today.

This paper makes four contributions:

- We show that full sandbox snapshots are a reliable restore primitive for coding-agent search. Across four Terminal-Bench anchor tasks, 24/24 restored continuations reproduced a valid live state, enabling agents to resume computation from intermediate trajectories (§5).
- We provide a matched-budget comparison between snapshot branching and independent retry. On our pre-registered harder Terminal-Bench subset, retry solves 17/25 tasks while snapshot-based search solves 6/25, establishing that reliable restoration alone is not sufficient to improve test-time scaling (§6).
- We identify concrete failure modes of environment-level search. Snapshot branching loses through budget fragmentation, selection of misleading intermediate states, agent handoff cost, and weak signals for deciding which states deserve further exploration (§8).
- We show that the value of snapshots depends on what information the environment contains. On extract-elf, compressed source-level state can outperform a full snapshot, while on a custom task whose progress lives in a SQLite database outside git, full snapshots solve 4/5 attempts and source-only restoration solves 0/5 (§7). These results suggest that environment-level search is most useful when progress cannot be reconstructed from repository state alone.



## 2. The Problem

A coding-agent trajectory changes more than source files. During execution, the agent may install packages, generate artifacts, populate databases, modify configuration, start services, or otherwise alter the machine in ways that affect future actions. A retry from the original repository loses all of this state, while a source-level checkpoint such as a git diff preserves only the subset represented in files under version control. This creates a simple question: **when an agent makes useful progress before failing, what state must we preserve to make that progress reusable?** If source state is sufficient, full-machine snapshots add unnecessary cost; if important progress lives elsewhere in the environment, source-only recovery cannot reconstruct the state the agent actually reached.

## 3. The Idea

The core idea is simple: instead of treating a failed coding-agent run as one indivisible attempt, treat it as a path through a sequence of machine states. As the agent works, some states are more promising than others: perhaps the bug has been reproduced, the right dependency is installed, or most of the fix is already in place. We periodically snapshot those states and store them in an archive. When a trajectory fails, we do not have to restart from the beginning; we can restore one of the archived states, place a new agent there, and continue exploring from that point. In this view, a sandbox snapshot plays the same role that a saved game does in search: it lets us return to a useful intermediate position and try a different continuation without replaying everything that came before. The important distinction is that the saved state is the entire execution environment, not just the agent’s text history or a patch. This gives the search procedure access to any progress encoded in the live machine, while leaving open the empirical question of whether that extra state is actually worth preserving.

![Figure 1. Four ways a later attempt can inherit state: retry from scratch, text and git patch, filesystem, and full sandbox snapshot.](figures/fig1-what-is-preserved.svg)

*Figure 1. What the next attempt starts from. (a) Retry from scratch uses the original repository. (b) Text and git patches keep notes and source diffs. (c) A filesystem checkpoint keeps files on disk. (d) A full sandbox snapshot keeps the live machine. We study (d) as a restore primitive.*

## 4. System and Evaluation

We evaluate two questions. First, can a coding agent reliably resume from an intermediate machine state? Second, does returning to such states improve task success compared with spending the same inference budget on independent retries?

### 4.1 Snapshot-based search

Our system wraps the agent's command-execution loop and periodically examines the current sandbox state. When the state satisfies a snapshot policy—for example, after the agent edits files or runs tests—we freeze the complete Daytona sandbox and add it to an archive.

The archive groups snapshots by simple behavioral features such as which files have been edited and whether tests have been run. For each group, it retains the highest-ranked snapshot.

A search begins with one root trajectory. After the root terminates, the system selects promising archived states, restores their sandboxes, and launches new child trajectories from those states. Each child receives the restored filesystem and machine state but a fresh agent context. Restoration is the Daytona snapshot itself: a child job starts from the recorded snapshot name rather than from the original task image.

![Figure 2. Go-Explore loop over sandbox snapshots: select, restore, explore, update archive.](figures/fig2-search-pipeline.svg)

*Figure 2. Search over Daytona sandboxes. (a) Select a snapshot from the archive. (b) Restore that sandbox (Go-Explore’s “go to state”). (c) A new agent explores from the restored machine. (d) New snapshots update the archive. Independent retry is the matched-budget baseline and is not shown.*

The comparison baseline is independent retry: spend the same total token budget on multiple trajectories that each begin from the original task state.

This design isolates the question we care about. Both strategies receive the same model and total inference budget; they differ primarily in whether later attempts begin from scratch or from previously reached environment states.

### 4.2 Experimental setup

Unless otherwise noted, all experiments use `anthropic/claude-haiku-4-5-20251001`, Terminal-Bench 2.0, Harbor, and Daytona sandboxes. We enforce budgets using a hard token limit.

We intentionally use a cost-efficient model under substantial budget pressure. If returning to useful intermediate states can avoid repeated work, this is a regime in which that advantage should be visible.

Our headline comparison uses five Terminal-Bench tasks whose single-attempt success rates fell between 20% and 80% during screening:

- git-multibranch
- extract-elf
- custom-memory-heap-crash
- code-from-image
- large-scale-text-editing

For each task we run five seeds with a total budget of one million tokens per seed. Retry divides this budget among three fresh attempts. Snapshot search runs one root trajectory followed by up to two restored children. The root receives 30% of the total budget, with the remainder available to children.

The headline protocol and task set were fixed before examining the final comparison.

## 5. Can an Agent Reliably Resume from a Snapshot?

Before evaluating search, we first test whether restoration itself works.

We select four Terminal-Bench tasks with high baseline solve rates and run three root trajectories per task. From these roots we launch 24 restored continuations.

All 24/24 continuations successfully restored their intended machine state. The fidelity extends beyond ordinary source files. In one fix-git example, restoring the sandbox reproduced an unresolved merge together with the corresponding Git index state.

Task success after restoration was also comparable to starting fresh:


| Role                  | Attempts | Solved     |
| --------------------- | -------- | ---------- |
| Root                  | 12       | 11 (91.7%) |
| Restored continuation | 24       | 21 (87.5%) |
| Fresh retry           | 36       | 31 (86.1%) |


Restored continuations therefore remain capable of solving the task after resuming from an intermediate environment. The experiment establishes restoration as a usable primitive; it does not establish an advantage over retry.

## 6. Does Returning to Promising States Beat Retry?

We next test our original hypothesis: under the same total token budget, can branching from promising intermediate states solve more tasks than repeatedly starting over?

The answer on our screened Terminal-Bench subset is no.

![Figure 3. Grouped bar chart of retry versus snapshot branching on five Terminal-Bench tasks. Retry 17/25, branching 6/25.](figures/fig3-headline-solve-rates.svg)

*Figure 3. Pre-registered headline comparison. Five file-centric Terminal-Bench tasks × five seeds, 1,000,000 tokens. Independent retry from scratch outperforms snapshot branching (17/25 versus 6/25). When useful progress is mostly in the filesystem, starting over is often enough. This total is frozen; later warehouse rows are not pooled into it.*


| Task                     | Independent retry | Snapshot branching |
| ------------------------ | ----------------- | ------------------ |
| git-multibranch          | 5/5               | 1/5                |
| extract-elf              | 4/5               | 3/5                |
| custom-memory-heap-crash | 3/5               | 1/5                |
| code-from-image          | 3/5               | 1/5                |
| large-scale-text-editing | 2/5               | 0/5                |
| **Total**                | **17/25 (68%)**   | **6/25 (24%)**     |


Retry wins on every task and solves nearly three times as many task-seed pairs overall.

Yet snapshot search is not simply failing to restore useful computation. In the headline experiment, we observe four cases where the root trajectory fails but a child restored from that root later succeeds: three on `extract-elf` and one on `custom-memory-heap-crash`.

We see the same recovery behavior in a separate follow-up experiment designed specifically to test failed roots. Snapshot branching rescues **67% of failed** `extract-elf` **roots** and **13% of failed** `regex-log` **roots**. In that experiment, independent retry solves **38% of seeds** on each task. Because this follow-up uses a different protocol, we report it separately from the headline comparison.

The mechanism therefore works in the narrow sense we intended: a failed trajectory can contain a state from which another agent succeeds. The problem is that, on the Terminal-Bench tasks we tested, these recoveries are not frequent enough to offset the cost of finding and exploiting those states.

## 7. What State Is Worth Preserving?

The headline experiment asks whether full snapshots improve search. A separate question is whether the full machine state itself contains information worth preserving.

We test this by comparing different ways of saving the same intermediate progress.

On `extract-elf`, saving the changed files is often enough. From the same checkpoint and with the same remaining token budget, a child started from a Git diff or from replayed commands can succeed even when the child started from the full snapshot runs out of budget. For this kind of task, most useful progress is already captured in the repository, so restoring the entire machine adds little.

We then construct `staged-service-repair`, a task where that is deliberately not true. During the task, useful progress is stored in a SQLite database at `/var/lib/inventory/store.db`. That database is outside the repository, so a Git diff cannot capture it.

We freeze a Daytona snapshot partway through the task and compare three ways of starting the next agent, all with the same remaining token budget of 200,000: a clean restart, a restart with the saved Git diff applied, and a restore of the full snapshot. In this checkpoint, the Git diff is empty because the code change has already been committed, while the lot code required by the verifier exists only in the database.

Starting from that same point, we compare the following conditions. 


| Seed      | Clean start | Git diff only    | Full snapshot |
| --------- | ----------- | ---------------- | ------------- |
| 0         | 0           | 0                | 1             |
| 1         | 0           | 0                | 0             |
| 2         | 0           | 0                | 1             |
| 3         | 0           | budget exhausted | 1             |
| 4         | 0           | 0                | 1             |
| **Total** | **0/5**     | **0/5**          | **4/5**       |


![Figure 4. Warehouse representation ablation: clean 0/5, git diff 0/5, full snapshot 4/5.](figures/fig4-warehouse-arms.svg)

*Figure 4. staged-service-repair, same planted checkpoint, 200,000 remaining tokens. The snapshot carries the warehouse database; the git patch does not. Not pooled with Figure 3.*

Here, preserving the environment changes the outcome. The Git diff does not contain the database state required by the verifier, while the snapshot does. Successful snapshot restorations solved the task using only **21k–41k tokens**, while clean restarts and Git-diff starts typically consumed more tokens and still failed, suggesting that restoring useful machine state can substantially reduce the inference needed to finish a task.

![Figure 5. Token use on the fifteen warehouse runs. Snapshot solves cluster at 21k–41k; several clean and diff failures spend far more.](figures/fig5-warehouse-tokens.svg)

*Figure 5. Token use at the same remaining cap. Filled markers solved. The square is a diff run that exhausted the 200k budget. Seed 1’s snapshot (open green) restored the database and still failed.*

The one snapshot failure is not a restore failure. On seed 1 the warehouse database was present, the agent read the remaining migration, started the HTTP server, and marked the task complete without applying that migration. A new agent in a restored machine still has to notice what work remains.

Together, these experiments suggest a clear boundary for when full-machine restoration is most useful: when important progress lives **outside the repository**, such as in databases, installed packages, running services, generated artifacts, or other machine state that cannot be recovered from Git or source files alone.

## 8. Why Does Snapshot Search Lose?

The negative headline result is highly structured. We observe four recurring failure modes.

![Figure 6. Four failure modes of snapshot search: budget split, sticky wrong state, handoff cost, and weak selection.](figures/fig6-failure-modes.svg)

*Figure 6. Why snapshot search still loses on file-centric tasks. (a) A fixed split starves the root or the children. (b) Restore is faithful to incorrect files. (c) The child inherits the machine, not the parent’s understanding. (d) Easy signals of activity are not the verifier.*

**Allocate budget adaptively.** Our current search splits a fixed token budget between the root and its children. This can leave the root with too little time to create strong checkpoints and leave children with too little time to finish. A better system could give more tokens to trajectories that show real progress and stop weak branches early.

**Detect promising checkpoints.** Snapshots preserve mistakes as well as useful progress. If a checkpoint contains a plausible but incorrect solution, the next agent may keep building on it. Better scoring could use tests, verifier signals, model-based judges, or learned value functions to identify states that are actually worth continuing from.

**Make handoffs cheaper.** Restoring the machine does not restore the previous agent's understanding of it. A child may still need to rediscover what changed, how to run tests, and what the parent was trying to do. In one case, a child used about 190,000 tokens over 26 steps, while a successful fresh retry used about 90,000 tokens over 11 steps. Better handoff summaries and snapshot metadata could reduce this repeated work.

**Learn which states are worth revisiting.** Our early selectors used simple signals such as file edits, successful commands, and locally passing tests. These signals are easy to measure, but they do not always mean that the task is closer to being solved. A stronger selector could combine machine state, test results, trajectory history, and verifier feedback to rank snapshots more accurately.

These results point to clear ways to improve environment-level search. Daytona makes it possible to freeze, restore, and branch from real coding environments. The next step is to improve budget allocation, checkpoint scoring, handoff quality, and state selection.

## 9. Threats to Validity

Our results cover one model tier and five screened Terminal-Bench tasks with five seeds each. The tasks were selected for intermediate baseline difficulty rather than sampled randomly, so the appropriate unit of generalization is the task rather than the individual trajectory.

Terminal-Bench is also largely file-centric. Tasks involving long-lived services, databases, caches, package installation, simulation state, or other persistent machine changes may place greater value on complete environment restoration. The staged-service-repair comparison uses one custom task, five seeds, and a planted checkpoint rather than a snapshot discovered during search.

Finally, we compare against independent retry rather than stronger search baselines such as best-of-N judging or SWE-Search, and we do not claim that the root/child budget allocation or snapshot-selection policy used here is optimal. 

## 10. Related Work

Our work sits at the intersection of test-time search for software agents, iterative program repair, and state-return methods from reinforcement learning. The main distinction we study is what gets preserved between attempts: text, source code, trajectories, or the complete execution environment.

**Test-time scaling for software engineering.** CodeMonkeys provides an inspiring demonstration of how much software agents can gain from additional test-time computation. It samples many editing trajectories, runs model-generated tests, and selects among candidate patches. The work shows that both serial and parallel test-time compute can substantially improve software-engineering performance (Ehrlich et al., 2025). SWE-Search takes a complementary approach by organizing search with Monte Carlo tree search, value estimation, and iterative feedback to decide which software states deserve more exploration (Antoniades et al., 2024).

Our work builds on this broader idea of spending computation more intelligently at test time. We focus on a different question. Instead of asking only how many trajectories to sample or how to score them, we ask what state a branch should resume from. In our system, a branch can inherit the complete live sandbox rather than reconstructing progress from repository state or agent context. Our results suggest that preserving more state is useful in some settings, but that good state selection and budget allocation are still essential.

**Iterative repair and memory.** RepairAgent is an important example of an autonomous repair system that can gather information, modify code, call tools, and validate candidate repairs through repeated interaction with a software environment (Bouzenia et al., 2024). Reflexion offers another influential approach to learning from failure. It converts feedback from previous attempts into textual reflections that guide future trials (Shinn et al., 2023).

These systems show that failed attempts can contain useful information that should not be discarded. Our work explores the same idea at the machine-state level. Textual memory or source patches may be enough when progress can be expressed in words or reconstructed from files. When progress lives in a database, installed dependency, service state, or another part of the machine, a full environment restore can preserve information that those lighter-weight methods cannot.

Agentless provides a valuable counterpoint. Xia et al. show that a relatively simple localization, repair, and validation pipeline can compete with more elaborate autonomous agents (Xia et al., 2024). We view this as an important lesson for our own work. More machinery is only worthwhile when it preserves something that matters. On the file-centric Terminal-Bench tasks we tested, independent retries remain stronger under the matched budget. On tasks with important state outside the repository, full snapshots become much more valuable.

**Returning to promising states.** Our search procedure is most directly inspired by Go-Explore. In this influential line of work, Ecoffet et al. show that exploration becomes easier when an agent can remember promising states, return to them reliably, and continue exploring from there (Ecoffet et al., 2019; 2021).

We bring that intuition into coding-agent environments by changing what a saved state means. In Atari, a cell represents a compact environment state. In our setting, the equivalent object is a live software sandbox containing files, installed dependencies, process state, databases, and other artifacts created during execution.

This setting introduces a new challenge. A perfectly restored state can still be a poor place to continue from. It may contain a wrong partial solution. The next agent may not understand how that state was reached. Revisiting it also consumes tokens that could have been spent on a fresh attempt. Our experiments therefore separate two questions. Can we restore the state faithfully? Is that state actually worth returning to?

**Positioning.** Prior work has shown strong results from preserving generated candidates, textual experience, and source-level progress. Our work adds full machine state to that design space. We do not argue that full snapshots are always better. Instead, we study when they preserve useful information that source files and textual memory miss. Our results suggest that this distinction becomes most important when progress extends beyond the repository.

## 11. Conclusion

Full sandbox snapshots let coding agents return to intermediate execution states that cannot always be represented by a patch or textual summary. Our experiments show that this capability is real, but its value depends on what the environment contains and whether the system can identify states that are actually worth revisiting.

For file-centric tasks, simpler representations and fresh retries are often enough. When progress lives in databases, services, installed dependencies, or other machine state outside the repository, full snapshots become more compelling.

The main open problem is therefore not restoration, but selection: how can we tell when a machine state represents reusable progress rather than a dead end? Better progress signals, cheaper handoffs between agents, and tasks with richer environment state are promising directions for making environment-level search useful in practice.

## References

Antoniades, A., Örwall, A., Zhang, K., Xie, Y., Goyal, A., and Wang, W. (2024). SWE-Search: Enhancing software agents with Monte Carlo tree search and iterative refinement. arXiv:2410.20285.

Bouzenia, I., Devanbu, P., and Pradel, M. (2024). RepairAgent: An autonomous, LLM-based agent for program repair. arXiv:2403.17134.

Ecoffet, A., Huizinga, J., Lehman, J., Stanley, K. O., and Clune, J. (2019). Go-Explore: A new approach for hard-exploration problems. arXiv:1901.10995.

Ecoffet, A., Huizinga, J., Lehman, J., Stanley, K. O., and Clune, J. (2021). First return, then explore. *Nature* 590:580–586.

Ehrlich, R., Brown, B., Juravsky, J., Clark, R., Ré, C., and Mirhoseini, A. (2025). CodeMonkeys: Scaling test-time compute for software engineering. arXiv:2501.14723.

Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., and Yao, S. (2023). Reflexion: Language agents with verbal reinforcement learning. arXiv:2303.11366.

Xia, C. S., Deng, Y., Dunn, S., and Zhang, L. (2024). Agentless: Demystifying LLM-based software engineering agents. arXiv:2407.01489.