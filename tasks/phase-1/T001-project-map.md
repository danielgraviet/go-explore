# T001: Project Map

## Goal

Turn the draft `docs/project-map.md` into a short repo map a new contributor can read in 5 minutes.

## Context

Use the existing notes in `docs/project-map.md`. Keep the tone simple and practical.

Useful references:

- `README.md`
- `docs/snapshot-strategy.md`
- `docs/phase-1-continuation-benchmark.md`
- `docs/daytona-snapshot-hook-bug.md`

## Scope

Update `docs/project-map.md` with:

- top-level folders and what they are for,
- main files under `go_explore/`,
- the snapshot-aware run flow,
- the continuation run flow,
- where to inspect outputs under `jobs/`.

## Out of Scope

- Do not refactor code.
- Do not add new behavior.
- Do not document every function or test.
- Do not write a long architecture essay.

## Suggested Starting Points

- `docs/project-map.md`
- `go_explore/cli.py`
- `go_explore/harbor.py`
- `go_explore/agents/factory.py`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/snapshots/`
- `go_explore/continuations.py`
- `go_explore/results.py`

## Acceptance Criteria

- One short table or bullet list for top-level folders.
- One short table or bullet list for key `go_explore/` files.
- Snapshot run flow is explained in 5-8 steps.
- Continuation flow is explained in 5-8 steps.
- Output artifacts under `jobs/` are named.
- Total doc stays concise. Target: under 120 lines.

## Validation

Reader should be able to answer:

- where Daytona snapshots are created,
- where continuation commands are planned,
- where Harbor job summaries are read.

## Notes / Open Questions

If a module boundary is unclear, add one bullet under `Open Questions`. Do not fix it in this ticket.
