# T002 Experiment 2: Screened Headline Benchmark — Candidate Pool Pre-registration

Pre-registered 2026-07-30, before any clean-screen result is inspected, per
`tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md`.

## Fixed settings (shared with Experiment 1 unless noted)

- Dataset: `terminal-bench@2.0`, environment: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`
- Model: `anthropic/claude-haiku-4-5-20251001`
- Aggregate token budget `B` = 500,000 (hard_token_limit), revised 2026-07-30
  to match Experiment 1's corrected value — B=150,000 caused real
  budget-exhaustion contamination in Experiment 1 for 2 of 4 anchors, which
  would corrupt this screen's core purpose (measuring genuine task
  difficulty, not budget artifacts).
- Task timeout: each task's own cached `agent_timeout_sec`/`verifier_timeout_sec`
  (from `go_explore.cli list-cached-tasks`), unchanged from Harbor's dataset
  defaults, fixed across all screen and headline runs for a given task.

## Screen design

For each candidate, 3 **independent clean repetitions at the full cap `B`**
(method=`single`, seeds 0/1/2 — each repetition gets the entire 150,000
budget, not a split share; this is a pass@3-at-fixed-budget clean solve
rate, not a retry arm). No branching is run or inspected during the screen.

## Candidate pool (14 tasks)

Selected from `go_explore.cli list-cached-tasks`, excluding: the four
Experiment 1 anchors, `fix-git`, the six tasks currently flagged
`invalid / snapshot-hook bug` in `docs/terminal-bench-task-log.md`
(`vulnerable-secret`, `sqlite-with-gcov`, `openssl-selfsigned-cert`,
`chess-best-move`, `largest-eigenval`, `financial-document-processor`),
`sqlite-db-truncate` and `sanitize-git-repo` (excluded from the headline set
by explicit rule unless they pass the screen — not spending screen budget on
them since prior branch data already showed 0/2 children), and
`qemu-alpine-ssh`/`qemu-startup` (excluded as a documented pre-existing
infrastructure/cost concern: prior unenforced runs consumed ~4.3M tokens,
making them very unlikely to be solvable or comparable at `B`=150,000, and
expensive just to screen).

| Task | Category | Difficulty | Snapshot-candidacy basis |
| --- | --- | --- | --- |
| `build-cython-ext` | debugging (setup/build) | medium | prior primary candidate; build-artifact-heavy state |
| `git-leak-recovery` | software-engineering (debugging) | medium | verified snapshot-capable root (task log: 1/1 root, 1/1 child) |
| `custom-memory-heap-crash` | debugging | medium | verified snapshot-capable root, mixed child outcomes (task log: 1/1 root, 1/2 children) |
| `code-from-image` | software-engineering (artifact-heavy) | medium | verified snapshot-capable root (task log: 1/1 root, 1/1 child) |
| `pytorch-model-recovery` | model-training (artifact-heavy) | medium | verified snapshot-capable root (task log: 1/1 root, 1/1 child) |
| `regex-log` | data-processing (debugging) | medium | verified snapshot candidacy via transcript arm; multiple competing hypotheses |
| `large-scale-text-editing` | file-operations (artifact-heavy) | medium | verified snapshot-capable root (task log: 1/1 root, timeout-prone child) |
| `merge-diff-arc-agi-task` | debugging | medium | not yet run; documented expectation — diff/merge debugging with file-edit and test-run commands matches the snapshot policy's trigger set |
| `multi-source-data-merger` | data-processing (artifact-heavy) | medium | not yet run; documented expectation — multi-stage file generation matches file-edit triggers |
| `db-wal-recovery` | file-operations (debugging) | medium | not yet run; documented expectation — forensic/recovery investigation matches investigation-command triggers |
| `git-multibranch` | system-administration (service) | medium | not yet run; documented expectation — git branch/merge commands are explicit policy triggers |
| `polyglot-c-py` | software-engineering (setup/build) | medium | not yet run; documented expectation — multi-language build/file-edit state |
| `gcode-to-text` | file-operations (artifact-heavy) | medium | not yet run; documented expectation — file generation/parsing matches file-edit triggers |
| `extract-elf` | file-operations (debugging) | medium | not yet run; documented expectation — binary inspection matches investigation-command triggers |

Mix: 2 setup/build, 6 debugging, 1 service, 5 artifact-heavy (some tasks span
more than one category informally; table lists primary category per the
cached-task metadata).

Per the ticket's selection rule, "verified snapshot-capable root path or a
documented reason" is applied when selecting the final ≤10 headline tasks
after screening — not as a pool-entry filter. It is recorded here per
candidate so the later selection step has it pre-registered rather than
assessed post-hoc.

## Screen outcome rules (fixed before any result is inspected)

- retain: 1–2 solves out of 3 (≈20–80% clean success)
- exclude: 0/3 (too hard at cap `B`), 3/3 (ceiling effect), missing
  archive/events or restore-relevant infrastructure failure, or
  timeout/infrastructure cost that makes the cap non-comparable
- select up to 10 of the retained tasks for the headline benchmark,
  preferring a mix of categories over the easiest survivors
- a task may be replaced only for a documented pre-existing infrastructure
  failure, with a same-category replacement chosen before its outcome is
  viewed

## Job naming

`t002-exp2-screen-<task>-single-seed-{0,1,2}`, manifests under
`docs/experiments/main-benchmark/manifests/t002-exp2-screen-<task>.json`,
analysis under
`docs/experiments/main-benchmark/analysis/t002-exp2-screen-<task>/`.
