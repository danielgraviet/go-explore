# Task System

This folder is the execution layer for Go-Explore work.

Use `docs/` for durable design notes and research writeups. Use `tasks/` for concrete work that someone can pick up, execute, validate, and hand back for review.

## Workflow

Task states:

- `backlog`: worth doing, not ready to start.
- `ready`: scoped enough for someone to pick up.
- `in-progress`: actively owned.
- `review`: implementation, experiment, or writeup is ready for review.
- `done`: accepted and linked from the backlog.

Keep `tasks/backlog.md` as the source of truth for status. Individual task files should contain the details needed to execute the work.

## Ticket Shape

Tickets should be outcome-oriented. They should give context and constraints without prescribing every step.

A good ticket includes:

- a clear goal,
- relevant code/docs to inspect,
- explicit out-of-scope boundaries,
- acceptance criteria,
- validation commands or expected artifacts,
- open questions where research judgment is welcome.

If a task is a spike, cap the time and require a written conclusion. If a task is implementation, require tests or a concrete artifact.

## Review Rhythm

For intern work, prefer small reviewable increments:

- 0.5-1 day for a spike or doc task,
- 1-3 days for an implementation or experiment task,
- one written result per experiment.

Each completed ticket should leave behind one of:

- a code change with tests,
- a committed doc or runbook,
- an experiment result with exact commands and paths,
- a short finding that closes an open question.
