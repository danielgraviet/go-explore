# Related-Work Citation Audit

Ticket: [tasks/phase-4/T005-related-work-citation-audit.md](../tasks/phase-4/T005-related-work-citation-audit.md).

This audit checks claims in the **archived** original essay
([docs/archive-docs/essay-original-hypothesis.md](archive-docs/essay-original-hypothesis.md))
and the **current** thesis ([docs/essay.md](essay.md)). No section
numbers are guessed. Uncertain items are marked **uncertain**.

Safe comparison for this project: prior systems search over **text,
diffs, git trees, or sampled final patches**. This work searches over
the **live sandbox**. Experiment A (S19) showed that on extract-elf,
a git diff can be enough; that does not license claiming we empirically
beat SWE-Search or Agentless.

## Sources

| Work | Cite as | Identifier | Primary source used |
| --- | --- | --- | --- |
| Go-Explore (preprint) | Ecoffet et al., 2019 | arXiv:1901.10995 | [arXiv HTML](https://ar5iv.labs.arxiv.org/html/1901.10995) |
| Go-Explore (Nature) | Ecoffet et al., 2021 | *Nature* 590:580–586, doi:10.1038/s41586-020-03157-9 | [author PDF](https://adrien.ecoffet.com/files/go-explore-nature.pdf) |
| Agentless | Xia et al., 2024 | arXiv:2407.01489 | [arXiv](https://arxiv.org/abs/2407.01489) |
| RepairAgent | Bouzenia, Devanbu, Pradel, 2024 | arXiv:2403.17134; ICSE 2025 | [arXiv HTML](https://arxiv.org/html/2403.17134) |
| Reflexion | Shinn et al., 2023 | arXiv:2303.11366 | [arXiv](https://arxiv.org/abs/2303.11366) |
| CodeMonkeys | Ehrlich et al., 2025 | arXiv:2501.14723 | [arXiv](https://doi.org/10.48550/arxiv.2501.14723) |
| SWE-Search | Antoniades, Örwall, Zhang, Xie, Goyal, Wang, 2024 | arXiv:2410.20285 | [arXiv HTML](https://arxiv.org/html/2410.20285v1) |

The original essay said "Reflection". The paper it meant is **Reflexion**
(Shinn et al.). Do not cite a generic "reflection" literature as if it
were one system.

## Per-work notes

### Go-Explore

**What it actually claims.** Hard exploration fails from *detachment*
(forgetting how to reach a visited state) and *derailment* (exploratory
noise while trying to return). Go-Explore remembers promising states,
returns to them, then explores. The 2019 preprint also uses a
deterministic simulator plus a later robustification phase. The 2021
Nature paper restates the family of algorithms and adds a
goal-conditioned policy variant for stochasticity. Results are Atari
(Montezuma's Revenge, Pitfall) and a pick-and-place robotics task.

**What we can say.** We use the same high-level return-then-explore
rule and change the definition of state from a simulator observation to
a full development sandbox.

**Do not say.** That Go-Explore "selects only a few states with a
trained model" as if that were the canonical algorithm. Archive
selection in Go-Explore is a research choice (heuristic, domain
knowledge, later policy); we should describe *our* selector, not
theirs. Do not claim we "apply Go-Explore to coding agents and it
works" — our headline comparison lost.

**Essay sentence:** "Go-Explore introduced the idea of solving hard
exploration problems by explicitly returning to promising states and
exploring from them." **Supported** by Ecoffet et al. 2021 abstract and
opening.

### Agentless

**What it actually claims.** Agentless is deliberately *not* an
autonomous tool-using agent. It runs a fixed three-phase pipeline:
hierarchical localization, patch generation (multiple diffs plus
reproduction tests), then validation/re-ranking. On SWE-bench Lite it
reported 32.00% (96 fixes) among open-source methods at low cost
(~$0.70 in the abstract's comparison). It argues that complex agent
loops are not required for that benchmark.

**What we can say.** Some coding systems preserve progress as localized
code context and candidate patches, without making the full environment
the search state.

**Do not say.** That Agentless "gives the model localized code context
and asks it to generate candidate patches" as if that were an agent
memory system. It is a staged, non-agent pipeline. Do not imply we
compared against Agentless empirically — we did not.

### RepairAgent

**What it actually claims.** An LLM agent for program repair on
Defects4J. It interleaves gathering information, gathering repair
ingredients, and validating fixes, guided by a finite state machine and
a tool set. 164 bugs repaired, 39 not fixed by prior techniques;
~270k tokens / ~$0.14 per bug at then-current GPT-3.5 pricing.

**What we can say.** Repair agents keep a *prompt* and tool trace that
is dynamically updated. That is compressed state, not a sandbox
snapshot.

**Do not say.** That RepairAgent searches over intermediate environment
snapshots. It does not. Do not cite Defects4J numbers as if they were
Terminal-Bench.

### Reflexion

**What it actually claims.** Agents verbally reflect on feedback and
store that text in an episodic memory buffer for later trials. No
weight updates. Gains on decision-making, coding (HumanEval pass@1 91%
in the paper's GPT-4 comparison), and reasoning.

**What we can say.** Memory/reflection systems preserve linguistic
summaries of prior attempts. Our context-ablation result (parent
summaries are expensive and did not rescue a bad regex snapshot) is
about *this* handoff, not a refutation of Reflexion.

**Do not say.** That Reflexion "maintains dynamic prompts" as a
catch-all for all memory agents. Cite the episodic verbal buffer
specifically. Do not use the HumanEval 91% number unless quoting
Reflexion's own eval.

### CodeMonkeys

**What it actually claims.** Test-time compute scaling on SWE-bench
via many multi-turn edit+test trajectories, then selection among
candidates (model-generated tests plus a selection trajectory). Serial
scaling = more iterations per trajectory; parallel scaling = more
trajectories. 57.4% on SWE-bench Verified at ~$2300; ensemble selection
66.2%.

**What we can say.** Best-of-N / parallel sampling of completed
trajectories is the family our retry baseline belongs to. CodeMonkeys
selects among **final edits**, not among restored machines.

**Do not say.** That we compared to CodeMonkeys. We compared to Harbor
retry-from-scratch, not their selection stack. Do not write "best-of-N
final-attempt selection" as if we ran CodeMonkeys.

### SWE-Search

**What it actually claims.** MCTS over a SWE-agent with a hybrid value
function (numeric + qualitative LLM feedback) and a discriminator
debate. Built on moatless-tools. **State space:** file context (spans)
plus a **git-like commit tree** so the agent can backtrack to a previous
codebase version. Tests run in Docker/K8s SWE-bench images; pods are
reset and a patch is applied. Reported 23% relative improvement on
SWE-bench Lite across five models versus open-source agents without
MCTS.

The git-like tree is in the paper's framework description: "operates in
a dynamic code environment with a flexible state-space and a git-like
commit tree structure" and the appendix note that moatless-adapted
stores code in git, each state referencing a commit and current patch.

**What we can say.** SWE-Search is the closest related system: it
searches intermediate coding-agent states and can return to a previous
**code** version. It does not snapshot the full live sandbox
(installed packages, non-git files, services, caches) as the restore
unit. Their testbed resets a pod and applies a patch.

**Do not say.** That SWE-Search "generally does not make the full
development environment the reusable unit of search" as a slight. Say
exactly: restore unit is git commit + file context + patch, not a
Daytona (or other) machine snapshot. Do not guess section numbers.
Do not claim our method beats SWE-Search; we never ran it.

**Uncertain:** whether every SWE-Search experiment used the git
backtrack path versus linear moatless-tools. The framework description
says the adapted tree is needed for MCTS backtracking. Flag as
framework-level, not necessarily every reported run.

## Original essay sentences

| Essay sentence (archived) | Verdict |
| --- | --- |
| "Go-Explore introduced the idea of solving hard exploration problems by explicitly returning to promising states and exploring from them." | **Keep.** Cite Ecoffet et al. 2021. |
| "We use the same high-level strategy but change the definition of state." | **Keep**, with the sandbox vs simulator qualifier. |
| "Some methods give the model localized code context and ask it to generate candidate patches." | **Soften.** This fits Agentless's localization+patch pipeline, not a generic "some methods." Name Agentless or drop. |
| "Others maintain dynamic prompts, reflections, or memory." | **Soften.** Cite Reflexion's verbal episodic memory. "Dynamic prompts" is too vague for RepairAgent. |
| "Test-time scaling systems sample many completed trajectories and select among final patches." | **Keep** as a family description. Cite CodeMonkeys as an example, and state we did **not** run it. Our baseline is independent Harbor retries. |
| "SWE-Search is closest in spirit because it searches over intermediate coding-agent states using a git-like tree." | **Keep**, citing arXiv:2410.20285 framework paragraph (git-like commit tree / commit+patch per state). |
| "These systems ... generally do not make the full development environment the reusable unit of search." | **Keep** if "full development environment" means packages, non-git artifacts, services, caches — which SWE-Search's pod-reset + patch loop does not restore. |
| "If full snapshots only match compressed state, then simpler approaches are preferable." | **Keep as a hypothesis.** Not yet tested (Experiment A). |

## Current thesis sentences

The rewritten [docs/essay.md](essay.md) does not name those systems in
the short public abstract. When the whitepaper related-work section is
drafted, use only the **Keep** rows above.

## Claims to remove from any draft

- Any implication that we empirically beat Agentless, RepairAgent,
  Reflexion, CodeMonkeys, or SWE-Search.
- "Best-of-N final-attempt selection" as a numbered experimental arm
  unless we actually run a judge/selector over final patches.
- Section numbers for any of these papers.
- "Reflection" as a paper title.
