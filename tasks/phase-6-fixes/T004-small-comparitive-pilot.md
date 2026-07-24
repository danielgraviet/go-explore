# T004 — Small comparative pilot (post-fix)

## Goal
Measure whether the T001 fix actually moves the two headline metrics:
solve-rate lift from branching, and token efficiency, on tasks that are
actually diagnostic (not `fix-git`, which is saturated — see phase-6
failure analysis).

## Tasks
- `regex-log` (known partial-progress dynamics, already instrumented)
- `sqlite`-related task (user-reported mixed results — better signal than
  a task that always passes or always fails)

Do not include `fix-git` as an evidence task; it may still run as a cheap
canary but its result doesn't count toward conclusions.

## Design
Per task, n=3-5 seeds, compare:
- `retry` (baseline)
- `promising_branch`, `context_mode=none`
- `promising_branch`, `context_mode=failure_symptom`

Use `plan-viability` / `run-viability-pilot` per `docs/runbook.md` rather
than hand-rolling manifests.

## Metrics to record
- Solve rate per arm per task.
- Total tokens per *successful* run (not just totals — a branch that fails
  cheaply is not "efficient," it's just cheap and wrong).
- For branch arms: is the selected/restored snapshot's step_id later than
  step 0 / than the root's first candidate (sanity check that T001 is
  actually engaging, using the same inspection as T003).

## Pass condition
Not a hard pass/fail gate — this is a measurement task. Write findings
back into `docs/phase6-failure-analysis.md` or a new dated follow-up doc.
Decide from results whether T006 (context-mode redesign) is warranted, or
whether the archive fix alone was sufficient.

## Status
Blocked on T001, T003.
