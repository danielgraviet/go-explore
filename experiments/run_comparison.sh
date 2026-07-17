#!/usr/bin/env bash
# Baseline vs. continuation comparison for one Terminal-Bench task.
#
# Baseline arm:     N independent snapshot-aware attempts (fresh sandbox each).
# Continuation arm: 1 root attempt (creates snapshots) + up to N-1 continuations
#                   forked from that attempt's snapshots.
# Same agent, same budget (N runs), different allocation of that budget.
#
# Usage: experiments/run_comparison.sh TASK N [MODEL]
#   e.g. experiments/run_comparison.sh chess-best-move 4
set -euo pipefail

TASK="${1:?usage: run_comparison.sh TASK N [MODEL]}"
N="${2:?usage: run_comparison.sh TASK N [MODEL]}"
MODEL="${3:-anthropic/claude-haiku-4-5-20251001}"

cd "$(dirname "$0")/.."
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"

DS="terminal-bench@2.0"
IMPORT="go_explore.agents.factory:snapshot_aware_terminus2_factory"
STAMP="$(date +%m%d-%H%M%S)"
PREFIX="cmp-${TASK}-${STAMP}"

echo "=================================================================="
echo " Comparison: task=${TASK}  N=${N}  model=${MODEL}"
echo " prefix=${PREFIX}"
echo "=================================================================="

echo ">>> [1/3] BASELINE: ${N} independent attempts"
harbor run --env daytona --jobs-dir jobs --n-attempts "${N}" --n-concurrent 1 \
  --dataset "${DS}" --task-name "${TASK}" --n-tasks 1 --model "${MODEL}" \
  --job-name "${PREFIX}-baseline" --export-traces --agent-import-path "${IMPORT}"

echo ">>> [2/3] CONTINUATION root: 1 attempt that lays down snapshots"
harbor run --env daytona --jobs-dir jobs --n-attempts 1 --n-concurrent 1 \
  --dataset "${DS}" --task-name "${TASK}" --n-tasks 1 --model "${MODEL}" \
  --job-name "${PREFIX}-root" --export-traces --agent-import-path "${IMPORT}"

echo ">>> [2b] continuations: fork up to $((N - 1)) snapshots from the root"
uv run python3 -m go_explore.cli continue-from-snapshots "jobs/${PREFIX}-root" \
  --job-prefix "${PREFIX}-cont" --max-snapshots "$((N - 1))" \
  --model "${MODEL}" --execute || echo "(no continuations — root may have made no snapshots)"

echo ">>> [3/3] SUMMARY"
uv run python3 experiments/summarize_comparison.py "${PREFIX}" "${N}"
