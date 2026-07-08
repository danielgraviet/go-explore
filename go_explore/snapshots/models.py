from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


CONTEXT_FILE_PATH = "/tmp/go_explore_context.md"
"""Well-known sandbox path for the running trajectory summary.

Written to the sandbox filesystem right before a Daytona snapshot is taken, so
it rides along as part of the snapshotted disk state. A child agent resumed
from that snapshot reads it back out to learn what the parent already tried.
"""


class SnapshotEvent(StrEnum):
    AGENT_STEP = "agent_step"
    COMMAND = "command"
    FILE_EDIT = "file_edit"
    TEST_RUN = "test_run"
    VERIFIER = "verifier"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    DISCOVERY = "discovery"


@dataclass(frozen=True)
class SnapshotCandidate:
    id: str
    event: SnapshotEvent
    environment_id: str | None = None
    restore_ref: str | None = None
    trace_path: Path | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    changed_files: tuple[str, ...] = ()
    command: str | None = None
    notes: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotHandle:
    """Reference returned by a backend after it captures environment state."""

    backend: str
    restore_ref: str | None = None
    environment_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotRecord:
    """Stored snapshot metadata with a short description for quick lookup."""

    candidate: SnapshotCandidate
    description: str
    backend: str = "metadata"

    @property
    def id(self) -> str:
        return self.candidate.id


@dataclass(frozen=True)
class ScoredSnapshot:
    candidate: SnapshotCandidate
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotContext:
    """Inputs available when deciding whether a point in a rollout is worth saving."""

    trial_name: str
    step_id: int
    source: str
    message: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    observation_text: str = ""
    trace_path: Path | None = None
    environment_id: str | None = None
    restore_ref: str | None = None
    trajectory_summary: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def context_from_atif_step(
    step: dict[str, Any],
    *,
    trial_name: str,
    trace_path: Path | None = None,
    environment_id: str | None = None,
    restore_ref: str | None = None,
) -> SnapshotContext:
    observation = step.get("observation") or {}
    observation_text = "\n".join(
        result.get("content", "")
        for result in observation.get("results", [])
        if isinstance(result, dict)
    )

    return SnapshotContext(
        trial_name=trial_name,
        step_id=int(step["step_id"]),
        source=step.get("source", ""),
        message=step.get("message", ""),
        tool_calls=tuple(step.get("tool_calls") or ()),
        observation_text=observation_text,
        trace_path=trace_path,
        environment_id=environment_id,
        restore_ref=restore_ref,
        metadata={
            "model_name": str(step.get("model_name", "")),
            "timestamp": str(step.get("timestamp", "")),
        },
    )
