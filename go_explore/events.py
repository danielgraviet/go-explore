from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENT_LOG_FILENAME = "events.jsonl"
EVENT_SCHEMA_VERSION = "go-explore-event-v1"
UNKNOWN_EXPERIMENT_ID = "unknown"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as file:
        file.write(json.dumps(event, sort_keys=True) + "\n")


def base_event(
    *,
    event_type: str,
    event_id: str,
    experiment_id: str | None,
    run_id: str,
    job_dir: Path | str,
    trial_name: str | None = None,
    task_id: str | None = None,
    step_id: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_type": event_type,
        "event_id": event_id,
        "experiment_id": experiment_id or UNKNOWN_EXPERIMENT_ID,
        "run_id": run_id,
        "job_dir": str(job_dir),
        "trial_name": trial_name,
        "task_id": task_id,
        "step_id": step_id,
        "timestamp": timestamp or utc_now_iso(),
    }
