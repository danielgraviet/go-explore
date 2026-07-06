from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CachedTask:
    name: str
    path: Path
    difficulty: str | None
    category: str | None
    agent_timeout_sec: float | None
    verifier_timeout_sec: float | None


def load_cached_tasks(cache_dir: Path) -> list[CachedTask]:
    tasks: list[CachedTask] = []
    for task_toml in sorted(cache_dir.glob("*/*/task.toml")):
        with task_toml.open("rb") as file:
            data = tomllib.load(file)

        metadata = data.get("metadata", {})
        agent = data.get("agent", {})
        verifier = data.get("verifier", {})

        tasks.append(
            CachedTask(
                name=task_toml.parent.name,
                path=task_toml.parent,
                difficulty=metadata.get("difficulty"),
                category=metadata.get("category"),
                agent_timeout_sec=agent.get("timeout_sec"),
                verifier_timeout_sec=verifier.get("timeout_sec"),
            )
        )

    return tasks

