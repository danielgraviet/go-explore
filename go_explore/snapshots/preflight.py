from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PREFLIGHT_TESTS_TARGET_DIR = "/tests"
PREFLIGHT_TEST_SCRIPT = "/tests/test.sh"
PREFLIGHT_CTRF_PATH = "/logs/verifier/ctrf.json"
PREFLIGHT_REWARD_PATH = "/logs/verifier/reward.txt"


@dataclass(frozen=True)
class PreflightVerificationResult:
    """Ground-truth result of running a task's own verifier against a restored
    sandbox before the agent's first turn.

    `unavailable` means no ground truth could be obtained (missing tests dir,
    unsupported OS, exec/upload failure, timeout, unparseable output) - callers
    must treat this the same as "no information", never as a failure signal.
    """

    status: Literal["passed", "failed", "unavailable"]
    tests_passed: int | None = None
    tests_failed: int | None = None
    tests_total: int | None = None
    failing_tests: tuple[str, ...] = ()
    exit_code: int | None = None
    error: str | None = None


async def run_preflight_verification(
    environment: Any,
    *,
    timeout_sec: float = 180.0,
) -> PreflightVerificationResult:
    """Run the task's own verifier script against `environment` right now and
    return a concrete pass/fail fact.

    Never raises - every failure mode collapses to `status="unavailable"` so a
    preflight check can never be worse than not having one.
    """
    try:
        return await _run_preflight_verification(environment, timeout_sec=timeout_sec)
    except Exception as error:  # noqa: BLE001 - last-resort safety net
        return PreflightVerificationResult(status="unavailable", error=str(error))


async def _run_preflight_verification(
    environment: Any,
    *,
    timeout_sec: float,
) -> PreflightVerificationResult:
    environment_dir = getattr(environment, "environment_dir", None)
    if not environment_dir:
        return PreflightVerificationResult(
            status="unavailable", error="environment has no environment_dir"
        )

    tests_dir = Path(environment_dir).parent / "tests"
    if not tests_dir.is_dir():
        return PreflightVerificationResult(
            status="unavailable", error=f"no tests dir at {tests_dir}"
        )

    env_os = getattr(environment, "os", None)
    if env_os is not None and str(getattr(env_os, "value", env_os)).lower() != "linux":
        return PreflightVerificationResult(
            status="unavailable",
            error="preflight_verification only supports linux tasks in v1",
        )

    upload_dir = getattr(environment, "upload_dir", None)
    exec_fn = getattr(environment, "exec", None)
    if upload_dir is None or exec_fn is None:
        return PreflightVerificationResult(
            status="unavailable", error="environment has no upload_dir/exec"
        )

    try:
        await upload_dir(source_dir=tests_dir, target_dir=PREFLIGHT_TESTS_TARGET_DIR)
    except Exception as error:  # noqa: BLE001
        return PreflightVerificationResult(
            status="unavailable", error=f"upload_dir failed: {error}"
        )

    try:
        await exec_fn(
            command=f"chmod +x {PREFLIGHT_TEST_SCRIPT}",
            user="root",
            timeout_sec=30,
        )
    except Exception:  # noqa: BLE001 - best-effort, not fatal
        pass

    try:
        exec_result = await asyncio.wait_for(
            exec_fn(command=PREFLIGHT_TEST_SCRIPT, timeout_sec=int(timeout_sec)),
            timeout=timeout_sec + 15,
        )
    except (TimeoutError, asyncio.TimeoutError):
        return PreflightVerificationResult(
            status="unavailable", error="preflight exec timed out"
        )
    except Exception as error:  # noqa: BLE001
        return PreflightVerificationResult(
            status="unavailable", error=f"exec failed: {error}"
        )

    exit_code = getattr(exec_result, "return_code", None)
    if exit_code is None:
        exit_code = getattr(exec_result, "exit_code", None)

    ctrf_summary = await _download_ctrf_summary(environment)
    if ctrf_summary is not None:
        tests_passed, tests_failed, tests_total, failing_tests = ctrf_summary
        # Prefer the actual test counts over the wrapper script's own shell
        # exit code: test.sh conventionally ends with `echo ... > reward.txt`,
        # whose exit code is always 0 regardless of whether pytest passed, so
        # exit_code is not a reliable pass/fail signal when CTRF data exists.
        status: Literal["passed", "failed"] = (
            "passed" if tests_failed == 0 else "failed"
        )
        return PreflightVerificationResult(
            status=status,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_total=tests_total,
            failing_tests=failing_tests,
            exit_code=exit_code,
        )

    if exit_code is not None:
        status = "passed" if exit_code == 0 else "failed"
        return PreflightVerificationResult(status=status, exit_code=exit_code)

    return PreflightVerificationResult(
        status="unavailable", error="verifier produced no exit code or ctrf output"
    )


async def _download_ctrf_summary(
    environment: Any,
) -> tuple[int, int, int, tuple[str, ...]] | None:
    download_file = getattr(environment, "download_file", None)
    if download_file is None:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        ctrf_path = Path(tmp_dir) / "ctrf.json"
        try:
            await download_file(PREFLIGHT_CTRF_PATH, str(ctrf_path))
            raw = ctrf_path.read_text()
            data = json.loads(raw)
            summary = data["results"]["summary"]
            tests_passed = int(summary["passed"])
            tests_failed = int(summary["failed"])
            tests_total = int(summary["tests"])
            failing_tests = tuple(
                test["name"]
                for test in data["results"]["tests"]
                if test.get("status") not in ("passed", "skipped")
            )
        except Exception:  # noqa: BLE001 - fall back to exit-code-only result
            return None

    return tests_passed, tests_failed, tests_total, failing_tests
