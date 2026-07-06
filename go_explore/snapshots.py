from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class SnapshotEvent(StrEnum):
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

