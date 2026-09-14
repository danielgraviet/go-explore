from __future__ import annotations

from pathlib import Path

from go_explore.snapshots.capture_diff import (
    GIT_REPO_DIFF_CMD,
    assert_parent_diff_artifact,
    host_diff_from_dirs,
    looks_like_git_usage,
    normalize_no_index_diff,
    parse_prebuilt_image,
)


def test_looks_like_git_usage_detects_help_text():
    help_text = (
        "warning: Not a git repository. Use --no-index to compare two paths "
        "outside a working tree\nusage: git diff --no-index [<options>] "
        "<path> <path>\n"
    )
    assert looks_like_git_usage(help_text)
    assert not looks_like_git_usage("diff --git a/x b/x\n")
    assert not looks_like_git_usage("")


def test_parse_prebuilt_image_from_job_log():
    log = (
        "Selected strategy: _DaytonaDirect\n"
        "Using prebuilt image: alexgshaw/extract-elf:20251031\n"
        "Both tmux and asciinema are already installed\n"
    )
    assert parse_prebuilt_image(log) == "alexgshaw/extract-elf:20251031"
    assert parse_prebuilt_image("no image here") is None


def test_normalize_no_index_diff_strips_temp_dir_names():
    raw = (
        "diff --git a/old/extract.js b/new/extract.js\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new/extract.js\n"
        "@@ -0,0 +1 @@\n"
        "+hello\n"
    )
    normalized = normalize_no_index_diff(raw)
    assert "a/extract.js" in normalized
    assert "b/extract.js" in normalized
    assert "a/old/" not in normalized
    assert "b/new/" not in normalized
    assert "a/new/" not in normalized


def test_host_diff_from_dirs_emits_applyable_new_file(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (new / "extract.js").write_text("console.log(1)\n")

    patch = host_diff_from_dirs(old, new)

    assert "diff --git a/extract.js b/extract.js" in patch
    assert "console.log(1)" in patch
    assert "a/old/" not in patch


def test_assert_parent_diff_artifact_rejects_usage_text(tmp_path):
    path = tmp_path / "parent.diff"
    path.write_text("usage: git diff --no-index [<options>] <path> <path>\n")
    try:
        assert_parent_diff_artifact(path)
    except SystemExit as exc:
        assert "git usage text" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_assert_parent_diff_artifact_accepts_empty_and_git_diff(tmp_path):
    empty = tmp_path / "empty.diff"
    empty.write_text("")
    assert_parent_diff_artifact(empty)
    real = tmp_path / "real.diff"
    real.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n")
    assert_parent_diff_artifact(real)


def test_git_repo_diff_includes_untracked_files():
    assert "git add -A" in GIT_REPO_DIFF_CMD
    assert "--cached" in GIT_REPO_DIFF_CMD
