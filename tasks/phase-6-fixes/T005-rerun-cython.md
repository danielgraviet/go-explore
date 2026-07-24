# T005 — Re-run build-cython-ext root (infra check, not a policy fix)

## Context
In the phase6 pilot, `build-cython-ext` promising_branch roots showed
`n_snapshots_created: 0` in `task-summary.csv`. Verified this is **not** a
snapshot-policy gap: the root job never executed at all —
`jobs/phase6-viability-pilot-build-cython-ext-promising-branch-none-.../result.json`
shows `n_completed_trials: 0`, stuck `pending`, no trial directory. A
separate `retry` run of the same task on the same day completed fine and
produced 7 archive cells with real `file_edit` candidates
(`jobs/phase6-viability-pilot-build-cython-ext-retry-.../archive.json`), so
the policy itself handles this task shape correctly.

## Task
Re-run the `build-cython-ext` promising_branch root once to confirm the
earlier failure was transient (Daytona/Harbor infra), not reproducible.

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name build-cython-ext \
  --n-tasks 1 \
  --job-name t005-build-cython-ext-root-retry \
  --export-traces
```

## Pass condition
`result.json` shows a completed trial (not stuck pending) and
`archive.json` has >0 entries. If it fails again the same way, check
`job.log` for the underlying Harbor/Daytona error before assuming policy
involvement.

## Do not
Do not modify `policies.py` for this task shape unless this re-run
reproduces a real classification gap (it currently doesn't look like one).

## Status
Done. `jobs/t005-build-cython-ext-root-retry`: `n_completed_trials: 1`
(not stuck pending like the earlier failure), reward 0.0 (task not solved
— hard task for haiku, expected, irrelevant to this check).

Archive produced 4 cells with real signal, including two `test_run`
candidates scoring 21.25 and 16.5 (well above the flat file-edit baseline
of ~1.25), plus a `file_edit` and a `command` cell. This confirms the
policy handles this task shape correctly and the earlier `n_snapshots_created: 0`
in the phase6 pilot was transient Harbor/Daytona infra failure, as
suspected — not a classification gap. No `policies.py` changes needed for
this task type.
