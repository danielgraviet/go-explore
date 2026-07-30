# T005: Measure Branch Search Diversity

## Goal

Measure whether restored continuations explore genuinely different states and
paths, rather than merely repeating their parent or siblings. Produce
deterministic, auditable diversity artifacts for each root-and-children branch
family and expose concise diversity fields in experiment analysis.

Diversity is a search-behavior metric, not a success claim. Report it beside
solve rate, token use, and validity; do not imply that a more diverse run is
better unless matched experiments show a corresponding outcome benefit.

## Context

The project claims that checkpoint/restore can reduce repeated work while
allowing multiple continuations to explore different approaches. Existing
artifacts partly support this:

- archive cell keys and selection events identify selected snapshots;
- `go_explore.repeated_work` detects exact/prefix command repetition and
  tracks setup, test, discovery, and sibling-repeat counts;
- analysis tables join limited repeated-work metrics into `run-summary.csv`.

They do not yet produce one branch-family view of selected-state diversity,
post-restore behavioral divergence, and final workspace-state overlap.
`unique_task_overlap` in `figure_tables.py` compares solve overlap across
methods; it is not branch-path diversity and must not be repurposed as such.

Relevant references:

- `docs/terminal-bench-task-log.md` filtering rule 5
- `go_explore/repeated_work.py`
- `go_explore/analysis_tables.py`
- `go_explore/figure_tables.py`
- `go_explore/events.py`
- `go_explore/continuations.py`
- `go_explore/snapshots/archive.py`
- `tasks/phase-7-fixes/T003-improve-state-selection.md`
- `tasks/phase-7-fixes/T004-stage-aware-branching.md`

## Scope

1. Define a deterministic branch-family identity: one root trial/run plus all
   continuation runs restored from that root. Use existing lineage fields; do
   not infer sibling relationships from job-name patterns alone.
2. Compute and persist selected-state diversity for each family:
   - number of selected continuations and number with verified restore lineage;
   - distinct snapshot cell keys;
   - distinct T004 primary stages when available;
   - pairwise changed-file-set Jaccard overlap among selected snapshots;
   - pairwise root-step distance between selected snapshots when step IDs are
     available.
3. Compute post-restore behavioral diversity from normalized command/event
   traces for the root and children:
   - exact command and command-prefix overlap of each child with its parent;
   - exact command and command-prefix overlap between siblings;
   - repeated setup, test, and discovery work, reusing the existing
     `repeated_work` definitions;
   - changed-file-set overlap and validation-command/result overlap where the
     trace supports them.
4. Capture a bounded final-state manifest for each completed root or
   continuation run. The manifest must contain only deterministic,
   non-sensitive identifiers:
   - changed task-workspace paths, subject to a configurable maximum;
   - stable content hashes for readable regular files within the task workspace;
   - paths omitted due to limits/errors and their reason;
   - final validation/test fingerprint and task outcome when available.
5. Compare final-state manifests within a branch family and report changed-path
   and content-hash overlap. Missing manifests are an explicit unknown value,
   not evidence of identical final states.
6. Write a versioned `branch-diversity.json` and a flat CSV/analysis table for
   each experiment. Include raw counts, denominators, missing-data status, and
   metric definitions. Join a compact subset into `run-summary.csv` and/or
   `task-summary.csv` without removing existing columns.
7. Add an aggregate figure table only when it preserves denominators and can
   distinguish observed zero diversity from missing artifacts.

## Out of Scope

- LLM, embedding, or semantic similarity scoring of commands, diffs, or final
  answers.
- Claiming that different commands/files necessarily represent different
  solution strategies.
- Changing snapshot selection, archive cells, stage assignment, context mode,
  branching budget, or continuation behavior.
- Capturing full workspace contents, secrets, credentials, model transcripts,
  or unbounded binary artifacts.
- Retrospectively fabricating final-state metrics for runs without the required
  artifacts.

## Implementation Guidance

- Treat every overlap as a set comparison with an explicit denominator. For
  non-empty sets, use Jaccard similarity `|A ∩ B| / |A ∪ B|`; represent an
  unavailable/unknown set as `null`, not `0.0`.
- Keep pure metric calculation separate from artifact collection and CSV/JSON
  rendering. Use small frozen dataclasses and typed fields for a family,
  per-child comparison, and final-state manifest.
- Reuse `command_prefix`, normalized `CommandObservation`, and
  `RunRepeatedWorkMetrics`; do not create a second inconsistent command
  parser.
- A child can legitimately repeat a validation command. Report it as observed
  repetition, not automatically as waste. Separate setup/test/discovery
  counts so interpretation remains possible.
- The final-state collector must operate only inside the task workspace,
  exclude directories/symlinks/special files, enforce path-count and byte-size
  limits before hashing, and never fail a task because collection failed.
- Use a standard stable digest such as SHA-256. Hashing identifies equality; it
  does not establish semantic similarity or correctness.
- Prefer artifacts already available after a Harbor run. If live workspace
  access is required, add a narrowly scoped best-effort capture hook with an
  explicit unavailable reason; do not use broad shell scans of the sandbox.
- Support archives before T003/T004: stage fields should be optional and
  reported as unavailable rather than guessed.
- Do not redefine `unique_task_overlap`; give the new output a distinct,
  unambiguous name such as `branch_diversity`.

## Suggested Starting Points

- Review lineage joins in `go_explore.analysis_tables` and
  `go_explore.continuations.ContinuationReport`.
- Extend pure repeated-work aggregation in `go_explore.repeated_work` to group
  root/sibling observations by family.
- Read snapshot selection metadata from archive/events rather than parsing
  names from continuation job directories.
- Identify the narrowest reliable workspace/artifact location exposed by a
  completed Harbor trial before adding final-state collection.
- Add output writing alongside existing analysis/figure-table generation, not
  as an ad hoc script in `jobs/`.

## Acceptance Criteria

- Every branch family with usable lineage receives a versioned diversity
  artifact containing selected-state, behavior, and final-state sections.
- The artifact records exact denominators and missing-data reasons for every
  overlap metric.
- Selected-state metrics include distinct cells, optional stages, selected-step
  distance, and changed-file overlap.
- Behavioral metrics distinguish parent-child and sibling overlap, and reuse
  the existing setup/test/discovery repetition definitions.
- Each completed run has either a bounded final-state manifest or a
  machine-readable unavailable reason. No workspace collection failure changes
  the task outcome.
- Final-state comparison reports path/hash overlap only when both manifests are
  available; it never treats missing data as equality or zero diversity.
- Analysis output has clearly named diversity fields/tables with no regression
  to existing solve, budget, lineage, or repeated-work columns.
- Aggregate output distinguishes `0` observed diversity from `unknown` due to
  missing traces/manifests.
- `uv run pytest -q` passes.

## Test Coverage

- Unit-test set/Jaccard calculations for identical, disjoint, partially
  overlapping, empty, and unavailable sets.
- Unit-test branch-family grouping from explicit lineage, including a root with
  zero, one, and two children; assert unrelated jobs are not grouped together.
- Unit-test selected-state metrics for distinct/same cell keys, stages, files,
  and root-step distances.
- Unit-test behavior metrics using synthetic normalized commands. Cover
  parent-only, sibling-only, exact-command, prefix-only, setup/test/discovery,
  and absent-trace cases.
- Unit-test final-state manifest collection using a temporary task workspace:
  deterministic hashes, path sorting, size/path caps, unreadable files,
  symlinks/directories, and collector failure. Assert no file outside the
  workspace is read.
- Unit-test final-state comparison with equal, disjoint, partial, and missing
  manifests.
- Regression-test JSON/CSV serialization and analysis joins, including legacy
  archives without T003/T004 stage fields and incomplete Harbor artifacts.
- Add/update figure-table tests only for the new explicitly named diversity
  output; retain the current meaning of `unique_task_overlap`.

## Validation

Run:

```bash
uv run pytest \
  tests/test_snapshot_replay.py \
  tests/test_continuations.py \
  tests/test_analysis_tables.py \
  tests/test_figure_tables.py -q
uv run pytest -q
```

Before review, generate a synthetic root-plus-two-children family with one
shared setup command, divergent post-restore edits, and one missing final-state
manifest. Inspect the JSON and CSV to verify that they report the expected
overlap values and preserve the missing-manifest reason.

## Notes / Open Questions

- Confirm whether Harbor retains a safe, task-workspace path after completion.
  If it does not, the first implementation may need a best-effort agent-side
  manifest capture hook. Keep that hook bounded and opt-in to the task
  workspace only.
- Final-state hashes can reveal file equality but not semantic equivalence.
  Keep all narrative interpretation in the result memo, not in the metric.
