# Go-Explore MVP
- can go-explore search algo be applied to coding agents?
- agent gets a task, we set deterministic critera to snapshot, if this agent fails, another agent picks up from selected snapshot and continues the task

# Things We Need
- Agent interface, need a cheap but capable agent to do some work on a task. 
- criteria for snapshotting, we need to define what is a good snapshot and how to select it.
- logic of restoring the snapshot. Use Daytona API + restore / fork feature.
- 3-5 candidate tasks. These could be SWE-bench or TBench tasks.

# MVP Direction

Use Terminal-Bench tasks through Harbor rather than authoring tasks from scratch.

- Terminal-Bench is the task corpus / benchmark.
- Harbor is the runner, task format, agent interface, environment interface, and dataset registry.
- Go-Explore is the experiment layer that decides when to snapshot, which snapshots to keep, and where to fork continuation attempts.
- Daytona is the first target environment backend for restore / fork behavior.

Keep Terminal-Bench or Harbor checkouts as sibling repos, not nested in this repo, unless we intentionally vendor a fork later.

```text
projects/
  go-explore/
  terminal-bench/
```

# First Experiment

Start with oracle and baseline Harbor runs before adding branching.

1. Confirm Harbor can run selected Terminal-Bench tasks locally or from the registry.
2. Run oracle attempts to understand task shape, job outputs, traces, and verification data.
3. Identify where Harbor exposes useful per-turn, per-command, or per-test hooks.
4. Add the thinnest adapter needed for deterministic snapshot events.
5. Compare independent attempts from scratch against continuations from selected snapshots.

# Baseline Comparison

For each selected task, compare:

- `N` independent attempts from the initial environment.
- `1` initial attempt plus `N - 1` continuations from selected snapshots.

Track:

- pass / fail,
- cost or token budget,
- wall-clock time,
- best validation result,
- selected snapshot metadata.

# Initial Snapshot Events

The first snapshot policy should be deterministic and simple:

- after an agent command,
- after a file edit,
- after a test or verification command,
- before timeout or failed completion,
- after any Harbor trace event that already contains reward or verifier output.

Selection starts heuristic-based:

- prefer passing or improved validation,
- prefer snapshots with relevant file changes,
- prefer snapshots after useful discovery commands,
- penalize large unrelated diffs,
- penalize missing verifier signal.

# Local Commands

Print the first oracle smoke command:

```bash
python -m go_explore.cli oracle-run --dataset terminal-bench-sample@2.0 --n-tasks 1 --n-concurrent 1 --job-name oracle-smoke
```

Summarize a Harbor job:

```bash
python -m go_explore.cli summarize-job jobs/oracle-smoke
```

List locally cached Harbor tasks:

```bash
python -m go_explore.cli list-cached-tasks
```

See `docs/task-selection.md` for the initial Terminal-Bench task shortlist and current runtime findings.

# Tests

Unit tests run by default:

```bash
uv run pytest -v
```

E2E tests invoke Harbor, Docker, Daytona, or model APIs and are skipped by default. Run them explicitly with either:

```bash
uv run pytest -k e2e -s
uv run pytest --run-e2e -s
```

# Possible Components
- Task Adapter: load task from T-bench. Prep env. run validation
- Agent Runner: give agent task prompt, let it act for a bounded budget.
- record transcript, commands, diffs, test results.
- Snapshot Manager: snapshot env at determinstic points, store snapshot, restore snapshot. Store metadata. 
- Snapshot Selector: start with heuristic ranking, choose top K. Build to interface, so can be replaced with a learned model, or FM.
- Explorer loop: run initial attempt. If fail, fork from selected snpashot and continue. Repeat until success or budget exhausted.
