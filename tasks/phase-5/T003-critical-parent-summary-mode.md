# T003: Critical Parent Summary Mode

## Goal

Add a context mode that gives the child parent history without implying that the parent was correct.

## Context

The current parent-summary prompt says the child is resuming work and should not repeat what was already tried. On failed roots, that can nudge the child to trust wrong state. We need a mode that frames parent work as untrusted evidence.

Depends on:

- P5-T002: Explicit Context Mode Controls

## Scope

Implement `context_mode=critical_parent_summary` for continuations.

The prompt should communicate:

- the restored state may be wrong,
- the parent attempt may have failed or have unknown reward,
- the child should independently audit files and assumptions,
- the child should not declare success solely because parent-local checks passed.

Record this mode in continuation reports, event/log artifacts, and analysis rows.

## Out of Scope

- Do not add verifier-aware snapshot scoring.
- Do not summarize the full transcript with an LLM.
- Do not run a paid Daytona smoke test in this ticket.

## Suggested Starting Points

- `go_explore/agents/snapshot_agent.py`
- `go_explore/continuations.py`
- `docs/continuation-context-modes.md`
- `tests/test_snapshot_agent.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- `critical_parent_summary` is accepted anywhere `parent_summary` is accepted.
- The child prompt differs materially from `parent_summary` and includes uncertainty/audit language.
- Tests assert the critical prompt does not contain language that implies prior work is correct.
- Docs describe when to use `critical_parent_summary`.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_snapshot_agent.py -q
```

Also inspect the generated prompt text in tests or fixtures.

## Notes / Open Questions

If parent reward is available at continuation-planning time, include it in the critical context. If not, explicitly say the parent reward is unknown.
