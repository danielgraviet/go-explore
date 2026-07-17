# The Archive

A cell keyed store of snapshots that allows us to make snapshots that we can rank and refork.
<img width="2538" height="1054" alt="image" src="https://github.com/user-attachments/assets/98b1131c-0ff2-4848-a00c-d18a5d8c88f3" />

## How it plugs in

The manager already takes a `store` implementing a `put`/`get`/`list` protocol, so we swap the default `InMemorySnapshotStore` for `ArchiveStore` — no manager changes. That's the whole integration:

```
manager.process_step(ctx)
      policy.candidates_for_step(ctx)     # some policy to fetch the best candidates
      backend.create_snapshot(...)        # freeze Daytona
      store.put(record)                   # now ArchiveStore
      archive.add(candidate)              # bucket into a cell
       → archive.save()                   # write jobs/<job>/archive.json
```

Separately, the continuation worker reads it back:

```
continue-from-snapshots --from-archive
  → SnapshotArchive.load(archive.json)
  → archive.select(k)                               # rank by score
  → harbor run --ek snapshot_template_name=<name>   # boot Daytona from it
```

## The two classes

- **`SnapshotArchive`** is a data structure, no Harbor/Daytona, fully unit testable. Methods: `add` / `select(k)` / `mark_selected` / `promote` / `save` / `load`.
- **`ArchiveStore`** is an adapter satisfying the store protocol so the manager needs no change; delegates to a `SnapshotArchive` and saves on every `put`.
<img width="1518" height="1198" alt="image" src="https://github.com/user-attachments/assets/f17c8d48-3ce5-4d27-8ab1-46f90274523a" />

The bolded functions/attributes are one's that are more selective to the archive itself, and not themselves helper/trivial.

## What are cells?

`cell_key_for(candidate)` is the set of files touched (`{a.py, b.py}`), or `<event>` when no file is named. Two snapshots with the same key are the same cell, and the archive keeps only the highest-scoring one: that's the dedup that keeps the archive small (this is the first initial idea for the policy itself). `select(k)` ranks by `score`, minus a penalty per prior fork so the frontier rotates instead of repicking one winner.

The archive stores pointers, not state (~1.2 KB/run from results). The machine lives in Daytona; `archive.json` only decides which snapshot to follow.

## Tests

`uv run pytest -q`

- `test_archive.py` — cell keying, `select` ordering, save/load tests
- `test_changed_files.py` — the `sed` fix, using the exact command from the run for the sanitize-git-repo test (more of an example to pull from).
