from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from go_explore.snapshots.archive import ArchiveEntry, SnapshotArchive


ArchiveSelectorMode = Literal[
    "list_order",
    "random",
    "archive_priority",
    "validated_progress",
    "partial_progress",
    "oracle",
]


@dataclass(frozen=True)
class ArchiveSelection:
    """A selected archive entry plus the metadata needed for experiment logs."""

    entry: ArchiveEntry
    selector_mode: ArchiveSelectorMode
    selector_reasons: tuple[str, ...] = ()


OracleLabels = Mapping[str, float | int | bool]


def load_oracle_labels(path: Path) -> dict[str, float]:
    """Load precomputed oracle labels keyed by snapshot name or archive cell key."""

    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Oracle labels must be a JSON object.")

    labels: dict[str, float] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError("Oracle label keys must be strings.")
        if not isinstance(value, (bool, int, float)):
            raise ValueError(
                f"Oracle label for {key!r} must be a number or boolean."
            )
        labels[key] = float(value)
    return labels


def select_archive_entries(
    archive: SnapshotArchive,
    *,
    mode: ArchiveSelectorMode = "archive_priority",
    k: int = 3,
    seed: int | None = None,
    oracle_labels: OracleLabels | None = None,
) -> list[ArchiveSelection]:
    """Select archive entries using one of the experiment baseline policies."""

    if k <= 0:
        return []

    entries = archive.entries()
    if mode == "archive_priority":
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=(
                    f"priority={entry.priority:.6g}",
                    f"score={entry.score:.6g}",
                    f"times_selected={entry.times_selected}",
                ),
            )
            for entry in archive.select(k)
        ]

    if mode == "validated_progress":
        eligible = [
            entry
            for entry in entries
            if entry.event in {"test_run", "verifier"}
            and (entry.tests_passed or 0) > 0
            and (entry.tests_failed or 0) == 0
        ]
        eligible.sort(key=lambda entry: (entry.priority, entry.score), reverse=True)
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=(
                    f"{entry.tests_passed} tests passed",
                    "0 tests failed",
                    "validated progress",
                ),
            )
            for entry in eligible[:k]
        ]

    if mode == "partial_progress":
        eligible = [
            entry
            for entry in entries
            if (
                entry.event in {"test_run", "verifier"}
                and (entry.tests_passed or 0) > 0
            )
            or entry.event == "discovery"
        ]
        eligible.sort(key=lambda entry: (entry.priority, entry.score), reverse=True)
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=_partial_progress_reasons(entry),
            )
            for entry in eligible[:k]
        ]

    if mode == "list_order":
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=("archive insertion order",),
            )
            for entry in entries[:k]
        ]

    if mode == "random":
        rng = random.Random(seed)
        shuffled = list(entries)
        rng.shuffle(shuffled)
        seed_reason = f"seed={seed}" if seed is not None else "seed=None"
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=(seed_reason,),
            )
            for entry in shuffled[:k]
        ]

    if mode == "oracle":
        if not oracle_labels:
            raise ValueError(
                "Oracle selector requires precomputed labels via --oracle-labels."
            )
        labeled = []
        for entry in entries:
            label = _oracle_label_for(entry, oracle_labels)
            if label is not None:
                labeled.append((entry, label))
        if not labeled:
            raise ValueError(
                "Oracle selector found no labels for archive snapshots or cells."
            )
        labeled.sort(key=lambda item: item[1], reverse=True)
        return [
            ArchiveSelection(
                entry=entry,
                selector_mode=mode,
                selector_reasons=(f"oracle_label={label:.6g}",),
            )
            for entry, label in labeled[:k]
        ]

    raise ValueError(f"Unknown selector mode: {mode}")


def _oracle_label_for(
    entry: ArchiveEntry,
    oracle_labels: OracleLabels,
) -> float | None:
    label = oracle_labels.get(entry.snapshot_name)
    if label is None:
        label = oracle_labels.get(entry.cell_key)
    if label is None:
        return None
    return float(label)


def _partial_progress_reasons(entry: ArchiveEntry) -> tuple[str, ...]:
    if entry.event == "discovery":
        return ("investigative discovery", "partial progress candidate")
    reasons = [f"{entry.tests_passed or 0} tests passed"]
    if entry.tests_failed is not None:
        reasons.append(f"{entry.tests_failed} tests failed")
    reasons.append("partial validation progress")
    return tuple(reasons)
