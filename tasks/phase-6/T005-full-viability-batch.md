# T005: Full Viability Batch

## Goal

Run the expanded Phase 6 viability benchmark after the pilot validates cost and artifact quality.

## Context

The full batch should produce enough data to judge whether sandbox snapshots create unique successes or meaningful cost/time savings over clean retries.

## Scope

- Run the approved 8-12 task set.
- Use matched seeds and planned budgets across methods.
- Center `context_mode=none` for branch continuations.
- Include `critical_parent_summary` as the primary context-bearing alternate.
- Keep any `parent_summary` runs small and explicitly diagnostic.
- Build normalized analysis tables and preserve execution reports.

## Out of Scope

- Do not change prompts or selectors mid-run.
- Do not expand the task set after inspecting early results.
- Do not write the final interpretation memo in this ticket.

## Suggested Starting Points

- `docs/experiments/viability-task-set.md`
- `docs/experiments/viability-pilot.md`
- `docs/runbook.md`

## Acceptance Criteria

- Every planned job is marked completed, failed, skipped, or blocked with a reason.
- Analysis tables exist for the full batch.
- Raw job paths, continuation reports, event logs, and costs are recorded.
- Any reruns are documented with exact reason and command.

## Validation

Build analysis tables from the final manifest and job directories. Inspect warnings before handing off to P6-T006.

## Notes / Open Questions

This ticket intentionally spends model and Daytona credits. Keep a running cost ledger and stop if failures are infrastructure-wide rather than task-specific.
