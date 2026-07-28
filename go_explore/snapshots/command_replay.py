"""Conservative, allowlisted replay of a parent's setup commands into a
fresh (`clean`) sandbox for `start_state_type="command_replay"` children.

Two phases, deliberately kept separate:

- `select_replay_commands` / `build_replay_manifest` (host-side, plan time):
  reads the parent's `trajectory.json` and decides *which* commands are
  even candidates for replay. Deterministic, no execution, no model call.
- `run_command_replay` (sandbox-side, setup time): actually execs the
  planned commands in the child's fresh sandbox, best-effort. Never raises
  and never blocks the agent from starting - a partially or fully failed
  replay is a result to measure, not an executor error, since replay is
  inherently an approximation of the parent's environment, not a guarantee.

Only dependency-install commands are candidates (`extract_signals_from_atif_step`'s
`dependency_installed` classification) - no build commands, service starts,
or general shell history. This is intentionally the narrowest allowlist that
could plausibly rebuild useful setup state; broadening it is a follow-up, not
part of this first cut.
"""

from __future__ import annotations

import json
import re
import shlex
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from go_explore.snapshots.replay import (
    extract_signals_from_atif_step,
    load_atif_trajectory_steps,
)

ReplayCommandStatus = Literal["planned", "replayed", "skipped", "failed"]
ReplayFinalStatus = Literal["planned", "completed", "unavailable"]

DEFAULT_MAX_COMMANDS = 8
DEFAULT_COMMAND_TIMEOUT_SEC = 120.0
DEFAULT_TOTAL_BUDGET_SEC = 300.0
REPLAY_OUTPUT_EXCERPT_MAX_CHARS = 300

# Shell metacharacters that would let a single "dependency install" command
# string smuggle in a second, unreviewed command when executed verbatim by a
# real shell (e.g. "pip install foo; rm -rf /"). Reject anything that isn't
# a single reviewable command, rather than trying to blocklist every
# dangerous substring.
_UNSAFE_PATTERN = re.compile(r"[;&|`]|\$\(")


@dataclass(frozen=True)
class ReplayCommandEntry:
    """One candidate command and its plan-time or execution-time outcome."""

    command: str
    dependency_manager: str | None = None
    packages: tuple[str, ...] = ()
    status: ReplayCommandStatus = "planned"
    skip_reason: str | None = None
    exit_code: int | None = None
    output_excerpt: str | None = None
    duration_seconds: float | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "dependency_manager": self.dependency_manager,
            "packages": list(self.packages),
            "status": self.status,
            "skip_reason": self.skip_reason,
            "exit_code": self.exit_code,
            "output_excerpt": self.output_excerpt,
            "duration_seconds": self.duration_seconds,
        }

    @staticmethod
    def from_json_dict(data: Mapping[str, Any]) -> ReplayCommandEntry:
        return ReplayCommandEntry(
            command=str(data["command"]),
            dependency_manager=data.get("dependency_manager"),
            packages=tuple(data.get("packages") or ()),
            status=data.get("status", "planned"),
            skip_reason=data.get("skip_reason"),
            exit_code=data.get("exit_code"),
            output_excerpt=data.get("output_excerpt"),
            duration_seconds=data.get("duration_seconds"),
        )


@dataclass(frozen=True)
class ReplayManifest:
    """The replay plan and (once executed) its outcome. Machine-readable and
    inspectable by design - this is the artifact `Validation` in T010 asks
    us to inspect directly before trusting a pilot run."""

    parent_job_dir: str
    parent_trial_name: str
    parent_artifact_path: str
    entries: tuple[ReplayCommandEntry, ...] = ()
    final_status: ReplayFinalStatus = "planned"
    total_replay_seconds: float | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "go-explore-replay-manifest-v1",
            "parent_job_dir": self.parent_job_dir,
            "parent_trial_name": self.parent_trial_name,
            "parent_artifact_path": self.parent_artifact_path,
            "final_status": self.final_status,
            "total_replay_seconds": self.total_replay_seconds,
            "entries": [entry.to_json_dict() for entry in self.entries],
        }

    @staticmethod
    def from_json_dict(data: Mapping[str, Any]) -> ReplayManifest:
        return ReplayManifest(
            parent_job_dir=str(data["parent_job_dir"]),
            parent_trial_name=str(data["parent_trial_name"]),
            parent_artifact_path=str(data["parent_artifact_path"]),
            final_status=data.get("final_status", "planned"),
            total_replay_seconds=data.get("total_replay_seconds"),
            entries=tuple(
                ReplayCommandEntry.from_json_dict(entry)
                for entry in data.get("entries") or ()
            ),
        )


def _is_unsafe_command(command: str) -> str | None:
    """Return a skip reason if `command` isn't safe to replay verbatim as a
    single shell exec, else None."""
    if _UNSAFE_PATTERN.search(command):
        return (
            "contains shell metacharacters (; & | ` $()) - not a single "
            "reviewable command"
        )
    try:
        shlex.split(command)
    except ValueError:
        return "not valid shell syntax (unbalanced quotes)"
    return None


def select_replay_commands(
    trajectory_path: Path,
    *,
    max_commands: int = DEFAULT_MAX_COMMANDS,
) -> list[ReplayCommandEntry]:
    """Select a conservative, allowlisted set of commands to replay: parent
    dependency installs only, deduplicated in first-seen order, filtered for
    shell-safety, and capped at `max_commands`. Every rejected command gets
    an explicit, auditable `skip_reason` - never a silent drop. Never
    raises - a missing or malformed trajectory yields no candidates.
    """
    try:
        steps = load_atif_trajectory_steps(trajectory_path)
    except (OSError, ValueError):
        return []

    agent_steps = [step for step in steps if step.get("source") == "agent"]

    entries: list[ReplayCommandEntry] = []
    seen_commands: set[str] = set()
    planned_count = 0
    for step in agent_steps:
        for signal in extract_signals_from_atif_step(step):
            if signal.event_type != "dependency_installed":
                continue
            command = signal.command or ""
            if not command or command in seen_commands:
                continue
            seen_commands.add(command)

            unsafe_reason = _is_unsafe_command(command)
            if unsafe_reason is not None:
                entries.append(
                    ReplayCommandEntry(
                        command=command,
                        dependency_manager=signal.dependency_manager,
                        packages=signal.packages,
                        status="skipped",
                        skip_reason=unsafe_reason,
                    )
                )
                continue

            if planned_count >= max_commands:
                entries.append(
                    ReplayCommandEntry(
                        command=command,
                        dependency_manager=signal.dependency_manager,
                        packages=signal.packages,
                        status="skipped",
                        skip_reason=(
                            f"replay budget exceeded (max {max_commands} commands)"
                        ),
                    )
                )
                continue

            entries.append(
                ReplayCommandEntry(
                    command=command,
                    dependency_manager=signal.dependency_manager,
                    packages=signal.packages,
                    status="planned",
                )
            )
            planned_count += 1

    return entries


def build_replay_manifest(
    trajectory_path: Path,
    *,
    parent_job_dir: Path,
    parent_trial_name: str,
    max_commands: int = DEFAULT_MAX_COMMANDS,
) -> ReplayManifest:
    entries = select_replay_commands(trajectory_path, max_commands=max_commands)
    return ReplayManifest(
        parent_job_dir=str(parent_job_dir),
        parent_trial_name=parent_trial_name,
        parent_artifact_path=str(trajectory_path),
        entries=tuple(entries),
        final_status="planned",
    )


def write_replay_manifest(manifest: ReplayManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_json_dict(), indent=2) + "\n")


def load_replay_manifest(path: Path) -> ReplayManifest:
    with path.open() as file:
        return ReplayManifest.from_json_dict(json.load(file))


async def run_command_replay(
    environment: Any,
    manifest: ReplayManifest,
    *,
    command_timeout_sec: float = DEFAULT_COMMAND_TIMEOUT_SEC,
    total_budget_sec: float = DEFAULT_TOTAL_BUDGET_SEC,
) -> ReplayManifest:
    """Replay `manifest`'s `planned` commands in `environment`, best-effort.

    Never raises: every command's outcome (`replayed`/`failed`) is recorded
    on its own entry, and running out of `total_budget_sec` marks any
    remaining `planned` commands `skipped` (with reason) rather than
    executing them late. Already-`skipped` plan-time entries pass through
    unchanged. This always runs in a fresh (`clean`) sandbox, not the
    parent's - replay is an attempt to rebuild useful state, not a
    guarantee, so callers must never treat a `failed`/`skipped` entry as an
    executor error.
    """
    exec_fn = getattr(environment, "exec", None)
    if exec_fn is None:
        unavailable_entries = tuple(
            entry
            if entry.status != "planned"
            else replace(
                entry, status="skipped", skip_reason="environment has no exec"
            )
            for entry in manifest.entries
        )
        return replace(
            manifest,
            entries=unavailable_entries,
            final_status="unavailable",
            total_replay_seconds=0.0,
        )

    updated_entries: list[ReplayCommandEntry] = []
    start = time.monotonic()
    budget_exhausted = False

    for entry in manifest.entries:
        if entry.status != "planned":
            updated_entries.append(entry)
            continue

        if not budget_exhausted and time.monotonic() - start >= total_budget_sec:
            budget_exhausted = True

        if budget_exhausted:
            updated_entries.append(
                replace(
                    entry,
                    status="skipped",
                    skip_reason=(
                        f"replay wall-clock budget exceeded ({total_budget_sec}s)"
                    ),
                )
            )
            continue

        command_started = time.monotonic()
        try:
            result = await exec_fn(
                command=entry.command,
                timeout_sec=int(command_timeout_sec),
            )
            exit_code = getattr(result, "return_code", None)
            if exit_code is None:
                exit_code = getattr(result, "exit_code", None)
            stdout = (getattr(result, "stdout", "") or "").strip()
            stderr = (getattr(result, "stderr", "") or "").strip()
            excerpt = (stderr or stdout)[:REPLAY_OUTPUT_EXCERPT_MAX_CHARS]
            status: ReplayCommandStatus = "replayed" if exit_code == 0 else "failed"
            updated_entries.append(
                replace(
                    entry,
                    status=status,
                    exit_code=exit_code,
                    output_excerpt=excerpt or None,
                    duration_seconds=time.monotonic() - command_started,
                )
            )
        except Exception as error:  # noqa: BLE001 - best-effort, must never raise
            updated_entries.append(
                replace(
                    entry,
                    status="failed",
                    output_excerpt=str(error)[:REPLAY_OUTPUT_EXCERPT_MAX_CHARS],
                    duration_seconds=time.monotonic() - command_started,
                )
            )

    return replace(
        manifest,
        entries=tuple(updated_entries),
        final_status="completed",
        total_replay_seconds=time.monotonic() - start,
    )
