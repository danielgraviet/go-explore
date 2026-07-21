# T004: Failure Case Audit

## Goal

Audit cases where snapshot continuation failed, hurt performance, or exposed misleading state/context.

## Context

Negative cases are central to improving the system and defending the paper. The early chess failure suggests continuation can be worse than restart when inherited context causes overtrust.

Depends on:

- P4-T002: Main Benchmark Execution

## Scope

Write `docs/experiments/failure-case-audit.md` categorizing failures into:

- state-fidelity failures,
- context-misuse failures,
- bad selector choices,
- snapshot/restore failures,
- model failures,
- benchmark or verifier issues.

Include concrete examples with run IDs, snapshots, and outcomes.

## Out of Scope

- Do not fix the failures in this ticket.
- Do not cherry-pick only favorable examples.
- Do not rerun tasks solely to improve outcomes.

## Suggested Starting Points

- `docs/archive-docs/results.md`
- continuation reports from P4-T002
- event logs from P2-T003

## Acceptance Criteria

- The memo includes at least 5 concrete examples if available.
- Each example links to run IDs, snapshots, and verifier outcomes.
- The memo separates implementation fixes from research limitations.
- The chess-style rubber-stamping failure is covered if reproduced.

## Validation

Cross-check examples against event logs, archive entries, and continuation reports.

## Notes / Open Questions

If fewer than 5 examples are available, include all available examples and explain why the sample is smaller.
