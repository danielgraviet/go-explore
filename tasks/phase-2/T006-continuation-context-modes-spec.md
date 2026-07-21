# T006: Continuation Context Modes Spec

## Goal

Specify continuation context modes so experiments can distinguish environment value from prompt or memory value.

## Context

Early continuation runs showed a failure mode where a child agent inherited misleading parent context and rubber-stamped a wrong answer. The essay needs experiments that separate full snapshot value from context-transfer value.

Relevant docs:

- `docs/essay.md`
- `docs/archive-docs/results.md`
- `go_explore/agents/README.md`

## Scope

Write `docs/continuation-context-modes.md` defining:

- original task only,
- parent summary,
- full transcript summary,
- diff only,
- diff plus transcript,
- command replay,
- full snapshot.

For each mode, describe inputs, expected artifacts, implementation status, likely failure modes, and whether it is an immediate implementation target.

## Out of Scope

- Do not implement the modes in this ticket.
- Do not change child-agent prompts.
- Do not run a live experiment.

## Suggested Starting Points

- `docs/essay.md`
- `docs/archive-docs/results.md`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/continuations.py`

## Acceptance Criteria

- Each mode has clear inputs and expected artifact shape.
- The doc explicitly covers context misuse and wrong-parent-state failures.
- The doc identifies which modes should be implemented first for Phase 3.

## Validation

Review the doc against the chess-style failure described in `docs/archive-docs/results.md` and the Claim 1 conditions in `docs/essay.md`.

## Notes / Open Questions

This is a spec ticket. Keep implementation choices concrete enough that P3-T002 can implement the first modes without redesigning the experiment.
