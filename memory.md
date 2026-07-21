# Harbor Agent Import Path Note

Harbor now expects `--agent` / `--agent-import-path` values to resolve to an agent class, not a factory function. Do not use `go_explore.agents.factory:snapshot_aware_terminus2_factory` for fresh snapshot-aware runs; it fails before trial execution with `TypeError: Imported agent ... must be a class`. Use `--agent go_explore.agents.factory:SnapshotAwareTerminus2` instead.
