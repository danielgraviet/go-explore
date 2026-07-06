"""Compatibility entrypoint for Terminal-Bench / Harbor experiments.

The active implementation lives under go_explore so this top-level benchmark
folder can stay thin while the repo is still taking shape.
"""

from go_explore.harbor import HarborRunConfig, build_harbor_command, run_harbor

__all__ = ["HarborRunConfig", "build_harbor_command", "run_harbor"]
