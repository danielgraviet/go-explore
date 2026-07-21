# T005: Related Work Citation Audit

## Goal

Verify the related-work claims used by `docs/essay.md`.

## Context

The essay currently references Go-Explore, Agentless, RepairAgent, Reflection, CodeMonkeys, and SWE-Search. Before it becomes a paper draft, exact claims and section references need to be checked.

## Scope

Write `docs/related-work-citation-audit.md` covering:

- paper links or bibliographic identifiers,
- relevant sections,
- what each work actually claims,
- what this project can safely claim in comparison,
- claims that should be softened or removed.

## Out of Scope

- Do not perform a full literature review.
- Do not rewrite the Related Work section.
- Do not add unsupported claims.

## Suggested Starting Points

- `docs/essay.md`
- `docs/snapshot-strategy.md`
- source papers for Go-Explore, Agentless, RepairAgent, Reflection, CodeMonkeys, and SWE-Search

## Acceptance Criteria

- Every related-work claim in `docs/essay.md` has a citation note or is flagged as unsupported.
- No section numbers are guessed.
- Uncertain claims are marked clearly.

## Validation

Manual source review. Include links or local citation notes sufficient for reviewer follow-up.

## Notes / Open Questions

This ticket may require internet access or local paper PDFs. Use primary sources only.
