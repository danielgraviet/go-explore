# Viability Task Set

This task set is for deciding whether Go-Explore-style snapshot continuation is
worth pursuing for coding agents under realistic test-time compute limits. It is
not optimized for favorable results. It deliberately mixes positive canaries,
known negative cases, setup-heavy tasks, reusable exploration tasks, and tasks
where restored state may be actively harmful.

The first benchmark question is narrow:

Can a branch policy that restores interesting sandbox snapshots solve tasks, or
solve them with meaningfully lower marginal cost, beyond what the same budget
would get from clean retry?

## Metadata Check

Validation command, run on 2026-07-22 from this repository:

```bash
.venv/bin/python -m go_explore.cli list-cached-tasks
```

The selected tasks below were present in the cached Harbor Terminal-Bench
inventory. The cache contains 91 raw entries and 90 unique task names; the only
duplicate observed in the listing is `chess-best-move`.

## Inclusion Rules

Include tasks that can expose at least one of these effects:

- setup or dependency state that a restored sandbox can reuse,
- intermediate diagnosis, generated artifacts, tests, or logs that may guide a
  child attempt,
- partial task-file edits that may either help or trap the child,
- nonzero clean-retry solve rate, so branch methods have a meaningful baseline,
- known negative behavior, so new methods can prove they fixed something.

Exclude tasks when they require unsupported credentials, manual intervention, or
very high timeouts that would dominate the first viability pass. Longer medium
tasks can be revisited after the pilot shows that the measurement path is stable.

## Selected Tasks

| Group | Task | Difficulty | Category | Agent timeout | Snapshot-help hypothesis | Likely failure mode | Pilot stop criteria |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| Easy canary | `fix-git` | easy | software-engineering | 900 | Restored snapshots should preserve a useful git conflict/index state and confirm the fork path still works. | Ceiling effect: clean retry and branch methods all solve, so there is no solve-rate headroom. | Stop after one seed if all methods solve and restore fields are complete. |
| Known hard negative | `regex-log` | medium | data-processing | 900 | New context and selector policies should avoid amplifying the known bad `/app/regex.txt` states. | Restored final-answer-file edits trap children in the same wrong regex basin. | Stop after one seed if continuations still fail while retry succeeds at least once; audit selected cells before spending more. |
| Clean retry sometimes succeeds | `sqlite-db-truncate` | medium | debugging | 900 | A root may discover the damaged database shape or repair path, and children may reuse that diagnosis. | Child inherits an incomplete or destructive database mutation and cannot recover. | Stop after one seed if all branches select destructive file-state cells without verifier-like evidence. |
| Reusable exploration state | `git-leak-recovery` | medium | software-engineering | 900 | Git history inspection and located leak commits are reusable across continuations. | Restoring a half-cleaned repo can hide the original evidence or confuse branch state. | Continue only if root snapshots include distinct git-inspection or validation cells. |
| Long setup or build artifacts | `build-cython-ext` | medium | debugging | 900 | Dependency installation, compiler output, and failing build logs should make later continuations cheaper. | Snapshot captures stale build artifacts or a locally patched environment that masks the true failing condition. | Stop if setup dominates and no child has lower environment plus agent time than retry. |
| Long setup or dependency-heavy | `pypi-server` | medium | software-engineering | 900 | Server/package setup and local publishing state may be expensive enough for snapshot reuse to matter. | Restored service state is stale, ports are occupied, or the child trusts a partially configured server. | Stop if restored jobs repeatedly fail from service state rather than task logic. |
| Reusable exploration state | `kv-store-grpc` | medium | software-engineering | 900 | Generated stubs, failing tests, and service wiring discoveries are plausible reusable progress. | Child inherits a wrong API shape and iterates around the parent mistake. | Continue only if selected snapshots distinguish build/setup cells from speculative implementation cells. |
| Final-answer-file risk | `sanitize-git-repo` | medium | security | 900 | Git object inspection and cleanup attempts are reusable, but final repo mutation is risky. | Snapshot preserves an irreversible-looking cleanup that removes needed evidence or fails hidden checks. | Stop if branches select final mutation cells before any validation signal. |
| Final-answer-file risk | `large-scale-text-editing` | medium | file-operations | 1200 | Partial edits may save work if the transformation is decomposable. | Restored partial edits create inconsistent mixed-format files that are harder to repair than scratch. | Stop if selected cells are bulk output edits with no independent sample validation. |
| Long setup or system state | `qemu-startup` | medium | system-administration | 900 | VM/system setup state is a natural snapshot target if restore is reliable and cheaper than setup. | Restored VM state is brittle, slow, or tied to transient process state. | Stop if restore overhead plus child repair time exceeds clean retry setup time. |

## Pilot Subset

Run a 3-task pilot before launching the full set:

| Task | Role In Pilot | Why |
| --- | --- | --- |
| `fix-git` | harness canary | Confirms branch creation, snapshot restore, lineage joins, and analysis tables still work. |
| `regex-log` | known negative | Tests whether `context_mode=none` and stronger measurement avoid repeating the Phase 4/5 failure. |
| `build-cython-ext` | setup-reuse probe | Gives the benchmark an early task where restored build/dependency state could plausibly reduce cost. |

The pilot should use clean retry, branch root, `promising_branch` with
`context_mode=none`, and `promising_branch` with
`context_mode=critical_parent_summary`. Keep `parent_summary` out of the main
pilot unless running a separate diagnostic ablation.

Pilot success does not require branch methods to win. It requires complete
lineage, restore overhead, snapshot overhead, token/cost, and outcome fields for
all planned rows. If branch methods lose, the run is still useful if the tables
show whether they lost because of bad selected state, context cost, restore
overhead, or ordinary model failure.

## Full Viability Batch

After the pilot produces clean artifacts, run the remaining seven tasks in
category-balanced order:

1. `git-leak-recovery`
2. `sqlite-db-truncate`
3. `pypi-server`
4. `kv-store-grpc`
5. `sanitize-git-repo`
6. `large-scale-text-editing`
7. `qemu-startup`

Use at least two seeds for tasks where the pilot or prior evidence suggests
clean retry has nonzero but nonsaturated solve rate. Use one seed first for
setup-heavy tasks where infrastructure failures could waste budget.

## Decision Criteria

Treat snapshot continuation as promising only if at least one of these holds on
the pilot plus full batch:

- branch methods solve tasks not solved by matched clean retry attempts under a
  comparable planned budget,
- branch methods match retry solve rate with lower total tokens plus lower
  wall-clock time after accounting for snapshot and restore overhead,
- analysis shows a repeatable class of useful cells, such as build setup,
  located failing tests, generated stubs, or validated intermediate artifacts.

Treat the current adaptation as not yet viable if:

- continuations mainly restore wrong final-answer files,
- selected cells lack validation evidence,
- restore overhead erases any token or setup savings,
- clean retry continues to solve while both branch contexts fail on the same
  tasks,
- the conclusions depend on `parent_summary`, whose Phase 5 cost was too high
  for the main benchmark.

## Fallbacks

If a selected task is unavailable or infrastructure-blocked before method-level
outcomes are inspected, replace within the same role:

| Blocked role | Preferred fallback | Reason |
| --- | --- | --- |
| setup/build task | `sqlite-with-gcov` | Build and instrumentation state should be reusable. |
| dependency/service task | `nginx-request-logging` | Service configuration with deterministic checks. |
| git/security task | `vulnerable-secret` | Security debugging with file and validation signals. |
| text/data task | `log-summary-date-ranges` | Data processing without the known `regex-log` failure mode. |

Record replacements before inspecting solve outcomes. Do not replace a task
because one method performs poorly.
