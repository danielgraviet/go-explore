# Code Preferences

> "Code is craft: the best version is useful, clear, and a little beautiful."

These preferences are here to make the project predictable. Small choices like names, imports, branches, and commit messages compound into easier reviews and fewer mistakes.

## Style

Use Google-style Python as the default:

- clear module, class, and function names,
- type hints on public boundaries,
- small functions with one job,
- docstrings for public APIs and non-obvious behavior,
- comments only when they explain why, not what.

Prefer boring, readable code over clever code.

## Imports

- Put `from __future__ import annotations` first when needed.
- Keep imports grouped: standard library, third-party, local.
- Prefer explicit imports over wildcard imports.
- Avoid importing heavy optional dependencies at module import time if tests or local tooling do not need them.

## Naming

- Use names that reveal intent: `root_job_dir`, `snapshot_name`, `trial_summary`.
- Avoid vague names like `data`, `result`, or `thing` unless the scope is tiny.
- Match existing project vocabulary: Harbor job, trial, snapshot, continuation, policy, backend.

## Branching

Keep branches focused:

- one ticket or bug per branch,
- no drive-by refactors,
- docs-only work should stay docs-only,
- experiment branches should record commands and result paths.

## Commits

Use concise Google-style commit messages:

```text
Add continuation report lineage fields.

The report previously required opening each branch job to understand which
snapshot it resumed from.

Record parent trial, snapshot name, continuation job, reward, and failure state
in the top-level report so Phase 1 results are easier to review.

Tested:
- uv run pytest tests/test_continuations.py -q
```

## Tests

- Run focused tests while developing.
- Run `uv run pytest -v` before handing off a meaningful code change.
- Do not require e2e tests for every change.
- If e2e tests are skipped, say why.

## Agent-Assisted Work

When using coding agents:

- keep tickets small,
- include acceptance criteria,
- inspect generated diffs,
- preserve user changes,
- leave commands and artifacts behind for review.
