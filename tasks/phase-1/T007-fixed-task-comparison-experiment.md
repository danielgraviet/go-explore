# T007: Fixed-Task Comparison Experiment

## Goal

Run one fixed Terminal-Bench task through a small baseline-vs-continuation comparison and write down what happened.

## Context

The project needs an early empirical check: do continuations from saved snapshots provide any visible benefit over independent attempts from scratch on a single task?

Depends on:

- T006: Continuation Report Polish

Relevant docs:

- `docs/task-selection.md`
- `docs/phase-1-continuation-benchmark.md`

## Scope

Choose one bounded task from the candidate list and run:

- a small number of independent baseline attempts from scratch,
- one snapshot-aware root attempt,
- a small number of continuations from selected snapshots.

Write `docs/experiments/fixed-task-comparison.md` with commands, job paths, costs if available, rewards, failures, and conclusions.

## Out of Scope

- Do not run the full Terminal-Bench dataset.
- Do not tune prompts extensively.
- Do not implement a learned selector.
- Do not claim statistical significance from one task.

## Suggested Starting Points

Candidate tasks:

- `openssl-selfsigned-cert`
- `regex-log`
- `large-scale-text-editing`
- `git-leak-recovery`
- `reshard-c4-data`

Use an easier task only if infrastructure is still unstable:

- `fix-git`
- `overfull-hbox`
- `hello-world`

## Acceptance Criteria

- The experiment doc includes exact commands.
- It links or names all relevant `jobs/` directories.
- It reports baseline outcomes and continuation outcomes separately.
- It states whether continuation helped, hurt, or was inconclusive.
- It identifies the next experiment or implementation fix.

## Validation

Use `go-explore summarize-job` or equivalent result inspection for each job.

If any live run fails for infrastructure reasons, record the failure and whether the task should be retried.

## Notes / Open Questions

This ticket is about learning, not proving the approach. A clean negative or inconclusive result is useful.
