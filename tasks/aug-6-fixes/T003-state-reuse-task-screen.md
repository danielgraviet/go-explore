# T003: Build a Measured Stateful-Task Screen from the Task Log

## Goal

Turn the existing Terminal-Bench task log into a small, pre-registered task
screen for experiments whose claim is specifically about Daytona full-sandbox
state reuse.

The screen must identify tasks where reusable setup/service/build/artifact
state is both materially expensive to recreate and reliably preserved by a
snapshot, while retaining enough clean-retry solve-rate headroom for a fair
branch-versus-retry comparison.

## Context

`docs/terminal-bench-task-log.md` already contains the right starting
knowledge. It records task hypotheses, prior root/child outcomes, snapshot
health, and known operational risks. It identifies candidates such as
`build-cython-ext`, `kv-store-grpc`, `pypi-server`, and
`nginx-request-logging`; it also records why some apparently stateful tasks,
such as `qemu-alpine-ssh`, are currently too expensive or noisy.

That log is an agent-readable historical registry, not a pre-registered
selection rule. Existing labels such as “setup/build” or “primary candidate”
are useful evidence but do not by themselves establish:

1. a clean retry actually repeats material setup work;
2. the corresponding state persists and works after Daytona restore; or
3. the task has enough solve-rate headroom to compare methods.

This ticket does not rediscover all Terminal-Bench tasks. It turns the current
log into a reproducible filter for a narrowly scoped state-reuse experiment.

Relevant references:

- `docs/terminal-bench-task-log.md`
- `docs/experiments/task-set.md`
- `docs/experiments/t002-exp2-screen-report.md`
- `docs/experiments/t002-exp1-result-memo.md`
- `docs/repeated-work-metrics.md`
- `docs/experiment-data-contract.md`
- `go_explore/repeated_work.py`
- `go_explore/analysis_tables.py`
- `tasks/aug-6-fixes/T001-grounded-preflight-selector.md`

## Scope

1. Create a short screen specification in `docs/experiments/` that fixes the
   inclusion/exclusion rules before any new branch outcomes are inspected.
2. Derive an initial candidate pool solely from existing task-log evidence.
   Record the exact task-log row/reason for every nominated task.
3. Define a small, measurable state-reuse eligibility table for each candidate:
   - **persistent state observed:** dependencies, build output, generated
     artifacts, service/configuration state, database/index state, or similar;
   - **restoration validity:** a restored child reaches the task environment
     and canonical verifier without snapshot fallback or known restore failure;
   - **repeated-work evidence:** matched clean attempts repeat setup/build/
     service/discovery work that the restored child does not need to repeat;
   - **setup materiality:** a pre-declared threshold for setup work, expressed
     as command counts and/or measured time, tokens, or wall-clock share;
   - **solve-rate headroom:** clean baseline is not a floor or ceiling under a
     fixed, hard token budget;
   - **operational health:** no unresolved recurring snapshot/Daytona/verifier
     failure that would confound a branch comparison.
4. Define a minimal screen run for candidates that lack one of these fields.
   It may collect clean-attempt and restored-checkpoint telemetry, but must not
   use branch success to decide whether a task belongs in the final set.
5. Produce a versioned candidate-screen table with one row per task, the
   observed evidence, inclusion decision, exclusion reason, artifact paths,
   and all missing-data reasons.
6. Select a small final state-reuse task set only by the pre-registered rules.
   Include at least one documented negative/control task when feasible, so the
   experiment can show where state reuse does *not* help.
7. Add a runbook section describing how future experiments should use this
   screen before claiming a Daytona state-reuse advantage.

## Out of Scope

- Re-running the entire 89-task Terminal-Bench registry.
- Changing snapshot selection, child context, root/child allocation, or
  Daytona infrastructure as part of the screen.
- Choosing tasks based on which branch arm later wins.
- Rewriting the historical task log or reinterpreting old results as if they
  were a pre-registered screen.
- Claiming a solve-rate improvement. This ticket only produces a defensible
  task set and evidence for a later matched experiment.
- Treating “setup-heavy” and “reasoning-heavy” as exclusive categories; many
  tasks involve both. The criterion is whether reusable sandbox state is
  demonstrably material.

## Pre-registered Selection Rules

Write exact thresholds in the screen specification before running any missing
telemetry. The first implementation should use simple, inspectable rules, for
example:

1. The task has an observed persistent-state milestone in an existing root or
   screen run.
2. At least one clean comparison repeats a setup/build/service command family
   or an equivalent expensive preparation step.
3. The repeated setup is material under a declared threshold. Start with a
   command-based threshold if token attribution is unavailable; do not invent
   token savings from a missing repeated-work report.
4. A snapshot-restored environment has reached the canonical verifier at least
   once without fallback/restore failure.
5. The clean fixed-budget baseline lies in a pre-declared non-floor/non-ceiling
   range. Use the same model, task timeouts, and hard-budget semantics intended
   for the later comparison.
6. Exclude tasks with unresolved recurring infrastructure failures, excessive
   per-run cost, or insufficient artifacts to establish the above facts.

The exact numerical thresholds are a research decision. They must be written
before gathering new screen outcomes and applied identically to every
candidate.

## Implementation Guidance

- Reuse `repeated_work` metrics and analysis-table joins. If existing logs do
  not support a metric, report `unknown` rather than estimating it manually.
- Separate historical evidence from newly collected screen evidence. Every
  table field should identify its source artifact and run date.
- Distinguish a task that is expensive because of reusable setup from one that
  is expensive because the model cannot reason through it. The former is a
  candidate; the latter is a floor-effect exclusion.
- Preserve near-ceiling tasks as restore-reliability controls when useful, but
  do not present them as solve-rate-headroom tasks.
- Do not use a root/child solve result as proof of state materiality. Inspect
  actual setup commands, artifacts, and restoration/verifier evidence.
- Keep the final set small enough for matched multi-seed execution. A strong
  first target is 2–4 eligible tasks plus one control, subject to the fixed
  rules and available budget.

## Deliverables

- `docs/experiments/state-reuse-task-screen-preregistration.md`
- `docs/experiments/state-reuse-task-screen-report.md`
- a machine-readable candidate table under `docs/experiments/` (CSV or JSON)
  with source artifact paths and decisions;
- an update to `docs/terminal-bench-task-log.md` that links each screened task
  to the new report without overwriting historical observations;
- a concise runbook addition for selecting tasks for state-reuse experiments.

## Acceptance Criteria

- The candidate pool is traceable to existing task-log entries, with no
  post-outcome task substitution.
- The preregistration defines materiality, restore validity, headroom, and
  operational-health rules before any new screen results are viewed.
- Every candidate table row contains observed evidence or an explicit unknown,
  source artifact paths, a decision, and an exclusion/inclusion reason.
- Repeated setup is measured from traces/events when available; unknown data is
  never reported as saved work.
- Final eligible tasks satisfy all fixed rules, and every exclusion is
  reproducible from the table.
- The report clearly separates: stateful-but-ceiling controls, stateful
  eligible headline candidates, stateful-but-flaky exclusions, and
  reasoning/floor-effect exclusions.
- The final report proposes no solve-rate result and does not alter the
  completed Experiment 2 analysis.

## Validation

1. Regenerate the candidate table from its declared source inputs and confirm
   stable ordering and decisions.
2. Manually audit at least one included task, one ceiling control, one
   infrastructure exclusion, and one floor/reasoning exclusion against their
   linked job/analysis artifacts.
3. Run relevant analysis/repeated-work tests after adding any extraction or
   table code:

```bash
.venv/bin/python -m pytest \
  tests/test_analysis_tables.py \
  tests/test_figure_tables.py -q
.venv/bin/python -m pytest -q
```

4. Before a paid matched experiment, review and freeze the preregistration,
   candidate table, final task list, model, budget, selector, and context mode.

## Follow-up

Use the final screened set for a separately registered comparison of clean
retry against snapshot continuation (for example, T001's
`grounded_partial_progress` selector). Report solve outcomes alongside setup
repetition, time to canonical verification, snapshot/restore overhead, and
the fraction of root failures recovered by children.
