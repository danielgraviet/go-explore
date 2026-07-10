# T002: Smoke-Test Runbook

## Goal

Create a repeatable runbook for local checks, e2e checks, and the first Harbor/Daytona smoke paths.

## Context

Several working commands already exist across the README and docs. They need to be consolidated so the intern can verify the project state before and after changes.

Relevant docs:

- `README.md`
- `docs/task-selection.md`
- `docs/daytona-snapshot-hook-bug.md`

## Scope

Write `docs/runbook.md` with:

- environment prerequisites,
- cheap unit-test command,
- e2e test command and required flags,
- Harbor oracle smoke command,
- snapshot-aware Terminus-2 command shape,
- job summary command,
- expected artifact locations,
- common failure modes and what they mean.

## Out of Scope

- Do not change the test suite unless a command in the runbook is broken.
- Do not add new CLI features.
- Do not require live Daytona/API runs for every local development change.

## Suggested Starting Points

- `README.md`
- `docs/task-selection.md`
- `docs/daytona-snapshot-hook-bug.md`
- `pyproject.toml`

## Acceptance Criteria

- `docs/runbook.md` exists.
- It distinguishes cheap tests from e2e tests.
- It explains that e2e tests may require Harbor, Docker, Daytona, and model credentials.
- It includes the correct custom-agent Harbor command shape: use `--agent-import-path` without also passing a built-in `--agent`.
- It lists where to inspect results under `jobs/`.

## Validation

Run the cheap validation command from the runbook and record the result in the task PR/commit message.

If e2e commands are not run, note why.

## Notes / Open Questions

Keep the runbook operational. Avoid turning it into a design document.
