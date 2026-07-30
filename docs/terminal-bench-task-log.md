# Terminal-Bench Task Log

Agent-readable registry of tasks used to adapt Go-Explore to coding agents
running in Terminal-Bench/Daytona. Update this file after every benchmark
batch. Record actual rewards and infrastructure quality; do not infer a win
from a task that every arm solves.

## Status vocabulary

- `primary`: useful for the main Go-Explore comparison.
- `canary`: useful for validating snapshots, lineage, or analysis, but has
  little solve-rate headroom.
- `negative`: useful for testing failure modes and state-selection safety.
- `candidate`: not yet sufficiently measured.
- `invalid`: artifacts are confounded by missing snapshots, empty diffs, or
  infrastructure failure and must not support a primary claim.

## Tasks run

| Task | Description / search-state hypothesis | Clean / root | Diff only | Diff + transcript | Diff + command log | Command replay | Full snapshot / branch | Status | Use next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fix-git` | Recover a lost commit and resolve a merge conflict. Git index, reflog, conflict state, and partial merge work are reusable, but the task is easy. | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1; GE children 2/2 | `canary` | Keep only for harness smoke tests |
| `regex-log` | Construct a regex for dates on lines containing valid IPv4 addresses; multiple dates, invalid dates, and false positives create competing hypotheses. | 0/1; GE root 0/1 | 0/1 | **1/1** | 0/1 | 0/1; replay had 0 entries | 0/1; GE children 0/2 | `negative` / `primary` for context ablations | Use for matched branch-vs-retry negative evidence; test multiple seeds |
| `build-cython-ext` | Clone, install, compile, and debug a Cython extension with dependency/version and build-artifact state. | GE root 0/1, timeout; 1.73M tokens | — | — | — | prior replay validation 0/1 | GE children 0/2; prior validated snapshot run succeeded once | `primary` | Use for setup-reuse and cost/overhead comparison |
| `git-leak-recovery` | Recover a leaked secret from Git history/object storage without damaging the repository. Git inspection and located commits are reusable intermediate state. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | critical-parent-summary child **1/1** (repeated: **1/1**); one eligible child both times | `primary candidate` | Get a second eligible child (archive currently only ever proposes one cell here) |
| `sqlite-db-truncate` | Diagnose and recover a truncated SQLite database. Database inspection and partial repair hypotheses may be reusable, but destructive states are risky. | promising-branch root **0/1** (repeated: **0/1**) | — | — | — | — | critical-parent-summary children **0/2** (repeated: **0/2**) | `negative candidate` (confirmed on repeat) | Stable negative across two independent batches; keep as a safety/negative anchor rather than spending more budget here |
| `kv-store-grpc` | Implement a small gRPC key-value service with generated stubs, dependencies, and test feedback. Setup artifacts and failing tests are reusable. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | critical-parent-summary children **2/2** (repeated: **2/2**) | `strong primary candidate` (confirmed on repeat) | Stable positive across two batches; good anchor for cost/efficiency reporting |
| `pypi-server` | Configure a local package index/server and publish or consume packages. Service and dependency setup may be reusable across branches. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | critical-parent-summary children **2/2** (repeated: **2/2**) | `strong primary candidate` (confirmed on repeat) | Stable positive; good anchor for cost/efficiency reporting |
| `nginx-request-logging` | Configure an Nginx service and request logging behavior. Service configuration and validation state may be reusable. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | critical-parent-summary children **2/2** (repeated: **2/2**) | `strong primary candidate` (confirmed on repeat) | Stable positive; good anchor for cost/efficiency reporting |
| `log-summary-date-ranges` | Process logs and summarize date ranges. Intermediate parsing/debugging work may be reusable without the regex-log trap. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | critical-parent-summary children **2/2** (repeated: **2/2**) | `strong primary candidate` (confirmed on repeat) | Stable positive; add a second seed |
| `sanitize-git-repo` | Inspect and sanitize a Git repository for sensitive content. Git investigation is reusable, but final cleanup can be irreversible. | promising-branch root **0/1** (repeated: **0/1**) | — | — | — | — | critical-parent-summary children **0/2** (repeated: **0/2**) | `negative / safety case` (confirmed on repeat) | Stable negative; keep as safety anchor |
| `large-scale-text-editing` | Apply a broad transformation across many files. Partial edits may help, but inconsistent intermediate state can be harmful. | promising-branch root **1/1** (repeated: **1/1**) | — | — | — | — | one child selected both times; **timed out both times** (1200s agent timeout, `AgentTimeoutError`) | `operational-risk case` (confirmed on repeat) | The child timeout is reproducible, not a fluke; retry with a longer per-agent timeout before drawing a solve-rate conclusion |
| `vulnerable-secret` | Locate and remediate a vulnerable secret. Repository inspection may dominate, so snapshot candidacy is uncertain. | promising-branch root **1/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; do not re-run until the hook fix lands |
| `sqlite-with-gcov` | Build or inspect SQLite with coverage instrumentation; generated/build artifacts may create reusable state. | promising-branch root **1/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; do not re-run until the hook fix lands |
| `openssl-selfsigned-cert` | Generate and validate a self-signed certificate. Files and configuration may persist, but the task may be too linear. | promising-branch root **1/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; do not re-run until the hook fix lands |
| `chess-best-move` | Analyze a position and produce a best move. Mostly computation/discovery with little persistent workspace state. | promising-branch root **0/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; the discovery-heavy hypothesis is no longer supported (offline replay found candidate states) |
| `largest-eigenval` | Compute a largest eigenvalue. Mostly numerical analysis with little persistent state. | promising-branch root **0/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; the discovery-heavy hypothesis is no longer supported (offline replay found candidate states) |
| `financial-document-processor` | Multi-stage extraction and artifact generation from a scanned/image document. | promising-branch root **0/1**; no archive/events | — | — | — | — | no children; runner stopped at `skipped_missing_archive` | `invalid / snapshot-hook bug` | See "Snapshot-hook failure" note below; do not re-run until the hook fix lands |
| `code-from-image` | Reconstruct working code from an image of source, then validate the generated artifact. | promising-branch root **1/1** | — | — | — | — | critical-parent-summary child **1/1**; one eligible child | `primary candidate` | Get a second eligible child; cheap task, good for repeat runs |
| `custom-memory-heap-crash` | Deep debugging of a heap crash with source changes and iterative test runs. | promising-branch root **1/1** | — | — | — | — | critical-parent-summary children **1/2** | `primary candidate` | Mixed child outcome (1 solved, 1 failed) from 38 candidate snapshots/2 forks — best current example of real branching producing different outcomes from the same root; inspect the two selected cells |
| `pytorch-model-recovery` | Recover a model/checkpoint and validate file/model state. | promising-branch root **1/1** | — | — | — | — | critical-parent-summary child **1/1**; one eligible child | `primary candidate` | Get a second eligible child |
| `qemu-alpine-ssh` | Multi-stage VM/network setup with persistent configuration state. | promising-branch root **0/1** | — | — | — | — | critical-parent-summary children **0/2** | `negative / high-cost candidate` | Most expensive task run so far (~4.3M tokens, ~73 min); confirm whether this is a real difficulty ceiling or a timeout/setup issue before spending more budget |

### Evidence notes

- `fix-git` is not a useful primary solve-rate task: all observed arms solve
  it. It remains valuable as the cheapest end-to-end snapshot/lineage canary.
- The `regex-log` transcript success is informative but the recent six-arm run
  used an empty diff and its full-snapshot arm used a missing snapshot fallback.
  Treat that batch as context-mechanism evidence, not clean full-snapshot
  evidence.
- The fresh Go-Explore pilot used current parent snapshots and verified each
  child with `Using snapshot: <parent snapshot>`. `fix-git` children solved
  2/2; `regex-log` children solved 0/2; `build-cython-ext` children solved
  0/2. This validates restoration but is only one root and two children per
  task, not a stable solve-rate estimate.
- `build-cython-ext` root setup was expensive and timed out, while children
  consumed fewer tokens than the root. This makes it a strong candidate for
  measuring reusable setup state, but it needs matched retry controls.
- `kv-store-grpc` is currently the strongest positive candidate: the root and
  both archive-selected `critical_parent_summary` children solved with real
  snapshot restoration and continuation lineage.
- `git-leak-recovery` is positive, but only one child was selected, so it is
  not yet evidence of robust branching or path diversity.
- `sqlite-db-truncate` is a useful negative/risk case: the root and both
  archive-selected children failed without infrastructure errors. The children
  restored distinct parent states but did not recover the database.
- `pypi-server`, `nginx-request-logging`, and `log-summary-date-ranges` are the
  strongest new positive candidates: each root and both selected children
  solved under `critical_parent_summary` with real snapshot restoration.
- `sanitize-git-repo` is a useful negative safety case: neither the root nor
  either child solved, so state reuse did not overcome the cleanup difficulty.
- `large-scale-text-editing` solved at the root, but its selected child timed
  out. Treat it as an operational-risk case until matched retry controls are
  measured.
- **Repeat batch (2026-07-29) confirms the strong/negative candidates are
  stable, not one-off.** `kv-store-grpc`, `pypi-server`,
  `nginx-request-logging`, and `log-summary-date-ranges` again solved at
  root and both selected children with real snapshot restoration.
  `sqlite-db-truncate` and `sanitize-git-repo` again failed at root and both
  children. `git-leak-recovery` again solved at root and its one eligible
  child (the archive still only ever proposes a single forkable cell for
  this task). `large-scale-text-editing` again solved at root, and its one
  selected child again failed — this time confirmed as a reproducible
  `AgentTimeoutError` after 1200s, not a one-off harness fault. These six
  tasks are now the most trustworthy primary/negative anchors in the set.
- Five new hard-root probes were run for the first time
  (`code-from-image`, `custom-memory-heap-crash`,
  `financial-document-processor`, `pytorch-model-recovery`,
  `qemu-alpine-ssh`). Three produced clean positive evidence with real
  branching (`code-from-image` 1/1 root + 1/1 child;
  `pytorch-model-recovery` 1/1 root + 1/1 child; `custom-memory-heap-crash`
  1/1 root + 1/2 children, the first task in this set where two children
  from the same root diverged in outcome). `qemu-alpine-ssh` branched
  correctly (40 snapshots created, 2 forked) but failed at root and both
  children, and is by far the most expensive task run so far (~4.3M tokens,
  ~73 minutes) — worth checking whether that is a genuine difficulty
  ceiling or a cost problem before using it further.
  `financial-document-processor` hit the snapshot-hook bug (see above) and
  is `invalid` for now.
- **Snapshot-hook failure, now root-caused (2026-07-29 batch).** Six roots
  across two batches (`chess-best-move`, `largest-eigenval`,
  `openssl-selfsigned-cert`, `sqlite-with-gcov`, `vulnerable-secret`,
  `financial-document-processor`) again produced no `archive.json` /
  `events.jsonl`, stopping the branch runner at `skipped_missing_archive`.
  This time each root's captured ATIF trajectory
  (`agent/trajectory.json`) was replayed offline through the live
  `InterestingAgentStepPolicy` (`go_explore/snapshots/policies.py`); every
  one of the six produced 1-6 snapshot-worthy candidates (file edits,
  verifier signals) that the live run never captured. That rules out "no
  interesting states" as the explanation — the policy logic is fine, but
  something in the live hook path (`SnapshotAwareAgent._hook_agent_loop` /
  `_process_step_snapshot` in `go_explore/agents/snapshot_agent.py`) or the
  Daytona snapshot backend silently did not fire or silently failed with no
  trace in `job.log` or `trial.log` (no "Warning: Snapshot processing
  failed" ever appears, in either the failing or the working runs, so
  absence of that print is not diagnostic). Five of the six failures
  clustered in one ~7-minute launch window (13:32-13:39 on 2026-07-29),
  right after a batch of 8 tasks in the same run that snapshotted correctly,
  which points at an intermittent/session-level failure rather than a
  per-task property. `docs/daytona-snapshot-hook-bug.md` documents a related
  but already-fixed issue (wrong agent instantiated when `--agent` and
  `--agent-import-path` were both passed) — this is a **new, still-open**
  failure mode. Treat these six tasks as `invalid` until the hook is
  instrumented with visible pass/fail logging (e.g. always write
  `archive.json` with an explicit empty-with-reason state, or log candidate
  counts per step) so a future run can tell "policy found nothing" apart
  from "hook never ran" without an offline replay. Do not re-run these
  tasks for primary evidence until then.
- The earlier hypothesis that `chess-best-move` and `largest-eigenval` are
  poor snapshot-search candidates because they are discovery/computation-heavy
  is **no longer supported**: offline replay found 3 and 6 snapshot-worthy
  steps in their captured trajectories respectively, consistent with the
  other four hook-failure tasks. Their zero-snapshot result looks like the
  same infrastructure bug, not a property of the task.

## Current experiment artifacts

| Batch | Analysis / evidence | Interpretation |
| --- | --- | --- |
| Claim 1 `fix-git` six-arm pilot | `docs/experiments/claim1-fix-git-pilot-analysis/` | All six solved; canary only |
| Claim 1 `regex-log` six-arm pilot | `docs/experiments/claim1-regex-log-pilot-analysis/` | Transcript solved; other arms failed; partly confounded |
| Go-Explore restoration pilot | `docs/experiments/ge-pilot-20260729-analysis/` | Current snapshots loaded; fix-git 2/2 children solved; no stable generalization yet |
| New critical-context branch probes | `jobs/ge-new-*-promising-branch-seed-0-root/` plus continuation reports | `kv-store-grpc` root and both children solved; `git-leak-recovery` root/child solved; `sqlite-db-truncate` root and both children failed |
| Five-task critical-context expansion | `jobs/ge-new-pypi-20260729-promising-branch-seed-0-root/`, `jobs/ge-new-nginx-20260729-promising-branch-seed-0-root/`, `jobs/ge-new-log-summary-20260729-promising-branch-seed-0-root/`, `jobs/ge-new-sanitize-20260729-promising-branch-seed-0-root/`, `jobs/ge-new-text-editing-20260729-promising-branch-seed-0-root/` | Three positive 3/3 root+children tasks, one negative safety task, and one child-timeout task |
| Repeat + expansion batch 2026-07-29 | `docs/experiments/ge-new-{chess,eigen,git-leak,kv-store,log-summary,nginx,openssl,pypi,sanitize,sqlite,sqlite-gcov,text-editing,vulnerable}-20260729/`, `docs/experiments/ge-hard-{code-from-image,custom-memory-heap-crash,financial-document-processor,pytorch-model-recovery,qemu-alpine-ssh}-20260729/` | Re-confirms the four strong-positive and two strong-negative tasks from the prior batch; confirms the `large-scale-text-editing` child timeout is reproducible; roots out the "discovery-heavy" snapshot-candidacy hypothesis in favor of a live snapshot-hook bug affecting 6/18 roots; adds three new positive hard-root probes, one mixed-outcome probe (`custom-memory-heap-crash`), and one expensive negative probe (`qemu-alpine-ssh`) |

## Candidate task pool

All tasks previously listed here now have at least one matched root/branch
measurement and have moved into the main table above. Remaining pool:

| Task | Expected signal | Initial role |
| --- | --- | --- |
| `qemu-startup` | Natural system-state reuse but high cost | defer; `qemu-alpine-ssh` (now measured, negative/high-cost) is a closer, cheaper proxy for this family — reconsider only if VM-state reuse becomes a specific claim to test |

New candidates should be added here as they are vetted in
`docs/experiments/viability-task-set.md`, before entering the primary set.

## Filtering rules for the main claim

1. Exclude ceiling-effect tasks such as `fix-git` from solve-rate headline
   results, but retain them as harness canaries.
2. Exclude a task from primary analysis if the intended snapshot was missing,
   silently replaced by a declarative build, or the parent diff was synthetic
   or empty.
3. Prefer tasks where clean retry has a nonzero but unsaturated solve rate and
   where parent trajectories contain reusable setup, diagnostics, artifacts,
   or validated intermediate states.
4. Run matched clean/retry and branch children through the branch runner so
   selection, lineage, snapshot cells, restore overhead, and path diversity
   are recorded in events and continuation reports.
5. Report both solve efficiency (successes per token/cost) and search behavior
   (distinct selected cells, commands, files, tests, and final states). A
   branch that merely repeats the parent is not evidence of diverse search.
6. Do not use a root with `skipped_missing_archive` and no `archive.json`/
   `events.jsonl` as evidence for or against Go-Explore, even if the root
   itself solved. Before assuming "no candidate states," replay the root's
   `agent/trajectory.json` offline through the current
   `InterestingAgentStepPolicy` — if that produces candidates the live run
   didn't capture, it is the still-open snapshot-hook bug (see evidence
   notes above), not a property of the task.
