from __future__ import annotations

import shlex
from typing import Protocol

from go_explore.snapshots.models import (
    ScoredSnapshot,
    SnapshotCandidate,
    SnapshotContext,
    SnapshotEvent,
)


class SnapshotPolicy(Protocol):
    """Pure decision function for turning rollout state into snapshot candidates."""

    def candidates_for_step(self, context: SnapshotContext) -> list[SnapshotCandidate]:
        ...


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

        if _looks_like_investigation(command_lower):
            event = event or SnapshotEvent.DISCOVERY
            notes.append("investigative command")

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

        if candidate.event == SnapshotEvent.DISCOVERY:
            score += 1.0
            reasons.append("captures an investigative discovery")

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


def _looks_like_investigation(command_text: str) -> bool:
    """Forensic/recovery/data-extraction tools: the discovery moments in tasks
    like file recovery or reverse engineering, which don't fit the file-edit
    or test-run heuristics above."""
    return any(
        token in command_text
        for token in (
            "strings ",
            "binwalk",
            "foremost",
            "photorec",
            "testdisk",
            "extundelete",
            "xxd",
            "od -",
            "od <",
            "hexdump",
            "dd if=",
            "unzip",
            "tar -x",
            "zipfile",
        )
    )


def _changed_files_from_commands(command_text: str) -> tuple[str, ...]:
    """Names of files a command batch wrote to.

    Extracts targets of `cat >`, `git add`, `sed -i` and `tee`. When an edit
    form is recognized by `_looks_like_file_edit` but its target cannot be named
    here, the step is tagged a file edit with no files, and callers that bucket
    by changed files (the archive's cell key) collapse unrelated states
    together — the failure mode that discarded 5 of 6 `sed` edits before this
    parsed them.

    Known unextractable: `apply_patch` and `python - <<HEREDOC`, whose targets
    live inside a patch body or script rather than in the command line. Steps
    using those still fall back to the coarse `<file_edit>` cell.
    """
    changed_files: list[str] = []
    for line in command_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat > "):
            changed_files.append(stripped.removeprefix("cat > ").split()[0])
        elif stripped.startswith("git add "):
            changed_files.extend(stripped.removeprefix("git add ").split())
        else:
            changed_files.extend(_edit_targets(stripped))
    return tuple(dict.fromkeys(_normalize_path(f) for f in changed_files if f))


def _normalize_path(path: str) -> str:
    """`./a/b.py` and `a/b.py` are the same file, so they must be the same cell."""
    return path.removeprefix("./").strip("'\"")


def _edit_targets(line: str) -> list[str]:
    """Trailing file operands of an in-place edit (`sed -i`, `tee`)."""
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []

    if not tokens:
        return []

    if tokens[0] == "sed":
        if not any(t.startswith("-i") for t in tokens[1:]):
            return []  # not in-place: reads, does not write
        return _operands_after_script(tokens[1:])

    if tokens[0] == "tee":
        return [t for t in tokens[1:] if not t.startswith("-")]

    return []


def _operands_after_script(tokens: list[str]) -> list[str]:
    """Drop flags and the sed script expression; what remains are the files."""
    operands: list[str] = []
    script_seen = False
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            # -e/-f take the script as a separate argument.
            if token in {"-e", "-f"}:
                skip_next = True
                script_seen = True
            continue
        if not script_seen:
            script_seen = True  # first bare operand is the script itself
            continue
        operands.append(token)
    return operands
