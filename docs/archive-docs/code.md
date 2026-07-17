# The Archive

A cell-keyed store of snapshots that turns "we made snapshots" into "we can rank and re-fork them." Full design: [`../snapshot-archive-proposal.md`](../snapshot-archive-proposal.md).

## How it plugs in

The manager already takes a `store` implementing a `put`/`get`/`list` protocol, so we swap the default `InMemorySnapshotStore` for `ArchiveStore` — no manager changes. That's the whole integration:

```
manager.process_step(ctx)
  → policy.candidates_for_step(ctx)     # interesting?
  → backend.create_snapshot(...)        # freeze Daytona
  → store.put(record)                   # ← now ArchiveStore
       → archive.add(candidate)         # bucket into a cell
       → archive.save()                 # write jobs/<job>/archive.json
```

Separately, the continuation worker reads it back:

```
continue-from-snapshots --from-archive
  → SnapshotArchive.load(archive.json)
  → archive.select(k)                   # rank by score
  → harbor run --ek snapshot_template_name=<name>   # boot Daytona from it
```

## The two classes

- **`SnapshotArchive`** — pure data structure, no Harbor/Daytona, fully unit-testable. Methods: `add` / `select(k)` / `mark_selected` / `promote` / `save` / `load`.
- **`ArchiveStore`** — thin adapter satisfying the store protocol so the manager needs no change; delegates to a `SnapshotArchive` and saves on every `put`.

## The one idea: cells

`cell_key_for(candidate)` is the set of files touched (`{a.py, b.py}`), or `<event>` when no file is named. Two snapshots with the same key are the same cell, and the archive keeps only the highest-scoring one — that's the dedup that keeps the frontier small. `select(k)` ranks by `score`, minus a penalty per prior fork so the frontier rotates instead of re-picking one winner.

The archive stores pointers, not state (~1.2 KB/run). The machine lives in Daytona; `archive.json` only decides which snapshot to follow.

## The cell-key fix

`_looks_like_file_edit` recognized `sed -i`, but `_changed_files_from_commands` only parsed `cat >`/`git add` — so a `sed` edit was tagged a file edit with no files and collapsed into the `<file_edit>` fallback. `_edit_targets` now parses `sed -i`/`tee` operands, skipping flags and the sed script, and `_normalize_path` folds `./a.py` and `a.py` into one cell.

Still unextractable (documented + tested): `apply_patch` and `python - <<HEREDOC`, where targets live inside a body or script, so those keep falling back.

## Tests

`uv run pytest -q`

- `test_archive.py` — cell keying, one-per-cell, keep-the-better, `select` ordering, frontier rotation, save/load, store-protocol conformance.
- `test_changed_files.py` — the `sed` fix, using the exact command from the run; pins the known-unextractable forms.
