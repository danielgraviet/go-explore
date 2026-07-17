"""Summarize one baseline-vs-continuation comparison run.

Reads the job dirs produced by run_comparison.sh for a given PREFIX and prints a
comparison table, then writes a markdown memo under docs/experiments/.

Usage:
    python experiments/summarize_comparison.py <PREFIX> <N>
"""

from __future__ import annotations

import sys
from pathlib import Path

from go_explore.results import summarize_job

JOBS = Path("jobs")
OUT_DIR = Path("docs/experiments")


def _passes(job_dir: Path) -> tuple[int, int, list[float | None]]:
    """Return (n_pass, n_total, rewards) for a job dir, or (0,0,[]) if missing."""
    if not (job_dir / "result.json").exists():
        return 0, 0, []
    summary = summarize_job(job_dir)
    rewards = [t.reward for t in summary.trials]
    n_pass = sum(1 for t in summary.trials if t.succeeded)
    return n_pass, len(summary.trials), rewards


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    prefix, n = sys.argv[1], int(sys.argv[2])

    # Baseline: one job with N independent attempts.
    base_pass, base_total, base_rewards = _passes(JOBS / f"{prefix}-baseline")

    # Continuation arm: the root attempt plus every continuation job.
    root_pass, root_total, root_rewards = _passes(JOBS / f"{prefix}-root")
    cont_dirs = sorted(JOBS.glob(f"{prefix}-cont-snapshot-*"))
    cont_pass = cont_total = 0
    cont_rewards: list[float | None] = []
    for d in cont_dirs:
        p, t, r = _passes(d)
        cont_pass += p
        cont_total += t
        cont_rewards += r

    arm_pass = root_pass + cont_pass
    arm_total = root_total + cont_total

    lines = [
        f"# Comparison: {prefix}",
        "",
        f"Budget: {n} agent runs per arm. Baseline = {n} independent attempts. "
        f"Continuation = 1 root attempt + {n - 1} continuations from its snapshots.",
        "",
        "| Arm | Solved | Attempts | Pass rate | Rewards |",
        "| --- | --- | --- | --- | --- |",
        f"| Baseline (independent) | {base_pass} | {base_total} | "
        f"{_rate(base_pass, base_total)} | {base_rewards} |",
        f"| Continuation (1 + forks) | {arm_pass} | {arm_total} | "
        f"{_rate(arm_pass, arm_total)} | root={root_rewards} conts={cont_rewards} |",
        "",
        f"Root attempt solved: {'yes' if root_pass else 'no'}. "
        f"Continuation jobs: {len(cont_dirs)}.",
        "",
        _verdict(base_pass, base_total, arm_pass, arm_total, root_pass),
    ]
    memo = "\n".join(lines) + "\n"
    print(memo)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{prefix}.md"
    out.write_text(memo)
    print(f"[written] {out}")
    return 0


def _rate(p: int, t: int) -> str:
    return f"{p}/{t} ({100 * p / t:.0f}%)" if t else "—"


def _verdict(bp: int, bt: int, ap: int, at: int, root_pass: int) -> str:
    if not bt or not at:
        return "**Verdict:** incomplete — a job dir is missing (check the run log)."
    if not root_pass and ap > bp:
        return (
            "**Verdict:** continuation helped — the root attempt failed, yet "
            "continuing from its snapshots solved more than independent restarts."
        )
    if bp == bt and ap == at:
        return (
            "**Verdict:** no signal — the baseline already solves it every time. "
            "Pick a harder task so continuation has room to show benefit."
        )
    if ap > bp:
        return "**Verdict:** continuation arm solved more than baseline."
    if ap < bp:
        return "**Verdict:** baseline solved more — continuation did not help on this task."
    return "**Verdict:** tie — no difference at this budget."


if __name__ == "__main__":
    raise SystemExit(main())
