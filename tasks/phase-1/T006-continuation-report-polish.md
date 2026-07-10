# T006: Continuation Report Polish

## Goal

Make the continuation report clear enough to judge whether continuation branches improved over the root attempt.

## Context

Phase 1 intentionally separates the Terminal-Bench root attempt from Go-Explore continuation branches. The report needs to preserve that distinction while making lineage and outcomes easy to inspect.

Relevant doc:

- `docs/phase-1-continuation-benchmark.md`

## Scope

Improve `continuation-report.json` generation so it clearly includes:

- root job path,
- root task and trial identifiers,
- selected snapshot names,
- continuation job names,
- parent snapshot for each continuation,
- reward or failure status for each branch,
- overall Go-Explore success/failure across branches.

Add or update tests around report shape where practical.

## Out of Scope

- Do not change Harbor scoring semantics.
- Do not implement snapshot ranking.
- Do not run a large benchmark.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/results.py`
- `go_explore/cli.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- The report can be read without opening every continuation job directory.
- Parent-child lineage is explicit.
- Branch failures are represented without crashing report generation.
- Tests cover the expected report fields or report parsing behavior.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py -q
```

If broader changes are made, also run:

```bash
uv run pytest -q
```

## Notes / Open Questions

Prefer additive report fields unless there is a strong reason to break existing consumers.
