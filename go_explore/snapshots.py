from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class SnapshotEvent(StrEnum):
    AGENT_STEP = "agent_step"
    COMMAND = "command"
    FILE_EDIT = "file_edit"
    TEST_RUN = "test_run"
    VERIFIER = "verifier"
    TIMEOUT = "timeout"
    FAILURE = "failure"


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
    metadata: dict[str, str] = field(default_factory=dict)


class SnapshotPolicy(Protocol):
    """Pure decision function for turning rollout state into snapshot candidates."""

    def candidates_for_step(self, context: SnapshotContext) -> list[SnapshotCandidate]:
        ...


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


class EveryAgentStepPolicy:
    """Naive baseline: snapshot after every agent step that can mutate state."""

    def candidates_for_step(self, context: SnapshotContext) -> list[SnapshotCandidate]:
        if context.source != "agent":
            return []

        return [
            SnapshotCandidate(
                id=f"{context.trial_name}:step-{context.step_id}",
                event=SnapshotEvent.AGENT_STEP,
                environment_id=context.environment_id,
                restore_ref=context.restore_ref,
                trace_path=context.trace_path,
                command=_joined_keystrokes(context),
                notes="agent step",
                metadata=_candidate_metadata(context, policy="every_agent_step"),
            )
        ]


class InterestingAgentStepPolicy:
    """Small deterministic policy for high-signal states before a learned model exists."""

    def candidates_for_step(self, context: SnapshotContext) -> list[SnapshotCandidate]:
        if context.source != "agent":
            return []

        command_text = _joined_keystrokes(context)
        observation = context.observation_text.lower()
        command_lower = command_text.lower()

        event: SnapshotEvent | None = None
        notes: list[str] = []

        if _looks_like_test(command_lower) or "passed" in observation or "failed" in observation:
            event = SnapshotEvent.TEST_RUN
            notes.append("validation signal")

        if _looks_like_file_edit(command_lower):
            event = SnapshotEvent.FILE_EDIT
            notes.append("file edit")

        if any(token in observation for token in ("conflict", "error", "traceback", "exception")):
            event = event or SnapshotEvent.COMMAND
            notes.append("error or conflict signal")

        if any(token in command_lower for token in ("git reflog", "git merge", "git commit", "git branch")):
            event = event or SnapshotEvent.COMMAND
            notes.append("git state transition")

        if "mark_task_complete" in command_lower:
            event = event or SnapshotEvent.VERIFIER
            notes.append("task completion signal")

        if event is None:
            return []

        return [
            SnapshotCandidate(
                id=f"{context.trial_name}:step-{context.step_id}",
                event=event,
                environment_id=context.environment_id,
                restore_ref=context.restore_ref,
                trace_path=context.trace_path,
                changed_files=_changed_files_from_commands(command_text),
                command=command_text,
                notes=", ".join(notes),
                metadata=_candidate_metadata(context, policy="interesting_agent_step"),
            )
        ]


class HeuristicSnapshotSelector:
    """Small deterministic selector for the first Go-Explore experiments."""

    def score(self, candidate: SnapshotCandidate) -> ScoredSnapshot:
        score = 0.0
        reasons: list[str] = []

        if candidate.tests_passed is not None:
            score += candidate.tests_passed
            reasons.append(f"{candidate.tests_passed} tests passed")

        if candidate.tests_failed is not None:
            penalty = min(candidate.tests_failed, 20) * 0.5
            score -= penalty
            reasons.append(f"{candidate.tests_failed} tests failed")

        if candidate.event in {SnapshotEvent.TEST_RUN, SnapshotEvent.VERIFIER}:
            score += 3.0
            reasons.append("has validation signal")

        if candidate.event == SnapshotEvent.AGENT_STEP:
            score += 0.25
            reasons.append("captures an agent step")

        if candidate.event == SnapshotEvent.FILE_EDIT:
            score += 1.0
            reasons.append("captures a file edit")

        if candidate.changed_files:
            score += min(len(candidate.changed_files), 5) * 0.25
            reasons.append(f"{len(candidate.changed_files)} changed files")

        if candidate.event in {SnapshotEvent.TIMEOUT, SnapshotEvent.FAILURE}:
            score -= 2.0
            reasons.append(f"terminal event: {candidate.event.value}")

        return ScoredSnapshot(candidate=candidate, score=score, reasons=tuple(reasons))

    def select(self, candidates: list[SnapshotCandidate], *, limit: int = 3) -> list[ScoredSnapshot]:
        scored = [self.score(candidate) for candidate in candidates]
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def _candidate_metadata(context: SnapshotContext, *, policy: str) -> dict[str, str]:
    return {
        **context.metadata,
        "policy": policy,
        "trial_name": context.trial_name,
        "step_id": str(context.step_id),
    }


def _joined_keystrokes(context: SnapshotContext) -> str:
    commands: list[str] = []
    for call in context.tool_calls:
        function_name = call.get("function_name", "")
        arguments = call.get("arguments") or {}

        if function_name == "bash_command" and isinstance(arguments, dict):
            commands.append(str(arguments.get("keystrokes", "")))

        elif function_name:
            commands.append(function_name)

    return "\n".join(command.strip() for command in commands if command.strip())


def _looks_like_test(command_text: str) -> bool:
    return any(token in command_text for token in ("pytest", "unittest", "npm test", "cargo test", "go test"))


def _looks_like_file_edit(command_text: str) -> bool:
    return any(token in command_text for token in ("cat >", "tee ", "apply_patch", "sed -i", "python - <<"))


def _changed_files_from_commands(command_text: str) -> tuple[str, ...]:
    changed_files: list[str] = []
    for line in command_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat > "):
            changed_files.append(stripped.removeprefix("cat > ").split()[0])
        elif stripped.startswith("git add "):
            changed_files.extend(stripped.removeprefix("git add ").split())
    return tuple(dict.fromkeys(changed_files))
