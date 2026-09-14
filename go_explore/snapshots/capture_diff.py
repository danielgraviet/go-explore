"""Capture a host-side patch from a Daytona snapshot for Claim 1 `diff_only`."""

from __future__ import annotations

import base64
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from daytona import (
    AsyncDaytona,
    CreateSandboxFromImageParams,
    CreateSandboxFromSnapshotParams,
)

PREBUILT_IMAGE_RE = re.compile(r"^Using prebuilt image:\s+(\S+)\s*$", re.MULTILINE)
GIT_REPO_DIFF_CMD = (
    "git add -A && (git diff --binary --cached HEAD || git diff --binary --cached)"
)


def looks_like_git_usage(text: str) -> bool:
    lowered = text.lstrip().lower()
    return (
        "not a git repository" in lowered
        or lowered.startswith("usage: git diff")
        or "use --no-index to compare" in lowered
    )


def parse_prebuilt_image(job_log: str) -> str | None:
    match = PREBUILT_IMAGE_RE.search(job_log)
    return match.group(1) if match else None


def normalize_no_index_diff(
    text: str, *, old_dir: str = "old", new_dir: str = "new"
) -> str:
    """Rewrite `git diff --no-index old new` paths so `git apply` works in workdir."""
    for name in (old_dir, new_dir):
        text = text.replace(f"a/{name}/", "a/")
        text = text.replace(f"b/{name}/", "b/")
        text = text.replace(f"--- a/{name}", "--- a")
        text = text.replace(f"+++ b/{name}", "+++ b")
    return text


def host_diff_from_dirs(old_dir: Path, new_dir: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "--no-pager",
            "diff",
            "--no-index",
            "--binary",
            str(old_dir.name),
            str(new_dir.name),
        ],
        cwd=old_dir.parent,
        check=False,
        capture_output=True,
        text=True,
    )
    text = result.stdout or ""
    if looks_like_git_usage(text) or looks_like_git_usage(result.stderr or ""):
        return ""
    return normalize_no_index_diff(text, old_dir=old_dir.name, new_dir=new_dir.name)


def assert_parent_diff_artifact(path: Path) -> None:
    text = path.read_text(errors="replace")
    if looks_like_git_usage(text):
        raise SystemExit(f"{path} is git usage text, not a patch")
    stripped = text.strip()
    if stripped and "diff --git" not in stripped and not stripped.startswith("--- "):
        raise SystemExit(f"{path} does not look like a unified diff")


async def capture_parent_diff(
    snapshot_name: str,
    output_path: Path,
    *,
    workdir: str = "/app",
    baseline_image: str | None = None,
) -> Path:
    """Boot `snapshot_name` just long enough to write a host-side git apply patch.

    Git checkouts include untracked files (`git add -A` then cached diff).
    Non-git workspaces diff against a clean sandbox from `baseline_image`.
    An empty patch is valid: the checkpoint had no file changes vs baseline.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncDaytona() as daytona:
        sandbox = await daytona.create(
            CreateSandboxFromSnapshotParams(
                snapshot=snapshot_name,
                auto_delete_interval=1,
            )
        )
        try:
            git_root = await _git_root(sandbox, workdir)
            if await _is_git_repo(sandbox, git_root):
                diff = await sandbox.process.exec(
                    GIT_REPO_DIFF_CMD,
                    cwd=git_root,
                    timeout=60,
                )
                text = diff.result or ""
                if looks_like_git_usage(text):
                    text = ""
                output_path.write_text(text)
                return output_path
            if not baseline_image:
                raise SystemExit(
                    f"{snapshot_name} has no git repo at {workdir}; pass "
                    "baseline_image so the non-git workspace can be diffed"
                )
            text = await _diff_against_image(
                daytona, sandbox, workdir, baseline_image
            )
            output_path.write_text(text)
        finally:
            await sandbox.delete()

    return output_path


async def _git_root(sandbox, workdir: str) -> str:
    root = await sandbox.process.exec(
        "git rev-parse --show-toplevel",
        cwd=workdir,
        timeout=30,
    )
    git_root = (root.result or workdir).strip() or workdir
    if getattr(root, "exit_code", 0) not in (0, None):
        return workdir
    return git_root


async def _is_git_repo(sandbox, git_root: str) -> bool:
    probe = await sandbox.process.exec(
        "git rev-parse --is-inside-work-tree",
        cwd=git_root,
        timeout=15,
    )
    return (probe.result or "").strip() == "true" and getattr(probe, "exit_code", 1) in (
        0,
        None,
    )


async def _diff_against_image(
    daytona,
    checkpoint,
    workdir: str,
    image: str,
) -> str:
    clean = await daytona.create(
        CreateSandboxFromImageParams(
            image=image,
            auto_delete_interval=1,
        )
    )
    try:
        old_files = await _checksums(clean, workdir)
        new_files = await _checksums(checkpoint, workdir)
        relpaths = sorted(set(old_files) | set(new_files))
        changed = [
            rel
            for rel in relpaths
            if old_files.get(rel) != new_files.get(rel)
        ]
        if not changed:
            return ""
        with tempfile.TemporaryDirectory(prefix="go-explore-diff-") as tmp:
            old_dir = Path(tmp) / "old"
            new_dir = Path(tmp) / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            for rel in changed:
                if rel in old_files:
                    _write_bytes(old_dir / rel, await _read_file(clean, workdir, rel))
                if rel in new_files:
                    _write_bytes(new_dir / rel, await _read_file(checkpoint, workdir, rel))
            return host_diff_from_dirs(old_dir, new_dir)
    finally:
        await clean.delete()


async def _checksums(sandbox, workdir: str) -> dict[str, str]:
    result = await sandbox.process.exec(
        "find . -type f ! -path './.git/*' -print0 | sort -z | xargs -0 sha256sum",
        cwd=workdir,
        timeout=60,
    )
    mapping: dict[str, str] = {}
    for line in (result.result or "").splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition(" ")
        rel = name.strip().lstrip("*").removeprefix("./")
        if rel:
            mapping[rel] = digest.strip()
    return mapping


async def _read_file(sandbox, workdir: str, relpath: str) -> bytes:
    quoted = shlex.quote(str(Path(workdir) / relpath))
    result = await sandbox.process.exec(f"base64 {quoted}", timeout=60)
    payload = (result.result or "").replace("\n", "").strip()
    if getattr(result, "exit_code", 0) not in (0, None) or not payload:
        return b""
    return base64.b64decode(payload)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
