"""Tests for extracting edited file names from a command batch.

Regression cover for the cell-key collapse observed on `sanitize-git-repo`:
`_looks_like_file_edit` recognised `sed -i`, but `_changed_files_from_commands`
could not name the file, so six distinct edits all bucketed into one
`<file_edit>` cell and the archive discarded five of them.
"""

from __future__ import annotations

from go_explore.snapshots.policies import (
    _changed_files_from_commands,
    _looks_like_file_edit,
)


def test_extracts_target_of_sed_in_place():
    # The exact command shape from the observed sanitize-git-repo run.
    cmd = "sed -i 's/AKIA1234567890123456/<your-aws-access-key-id>/g' ./ray_processing/process.py"
    assert _changed_files_from_commands(cmd) == ("ray_processing/process.py",)


def test_sed_edits_to_different_files_are_different_cells():
    """The bug: these six collapsed into one cell because none named a file."""
    batch = "\n".join(
        [
            "sed -i 's/AKIA123/<aws-key>/g' ./ray_processing/process.py",
            "sed -i 's/D4w8z9/<aws-secret>/g' ./ray_processing/ray_cluster.py",
            "sed -i 's/ghp_aBc/<github-token>/g' ./ray_processing/config.yaml",
        ]
    )
    assert _changed_files_from_commands(batch) == (
        "ray_processing/process.py",
        "ray_processing/ray_cluster.py",
        "ray_processing/config.yaml",
    )


def test_sed_without_in_place_flag_changes_nothing():
    # `sed` that only reads must not be reported as an edit target.
    assert _changed_files_from_commands("sed 's/a/b/' input.txt") == ()


def test_sed_with_separate_script_flag():
    assert _changed_files_from_commands("sed -i -e 's/a/b/' notes.md") == ("notes.md",)


def test_sed_with_suffixed_in_place_flag():
    assert _changed_files_from_commands("sed -i.bak 's/a/b/' notes.md") == ("notes.md",)


def test_sed_with_multiple_file_operands():
    assert _changed_files_from_commands("sed -i 's/a/b/' one.py two.py") == (
        "one.py",
        "two.py",
    )


def test_extracts_tee_target():
    assert _changed_files_from_commands("tee -a /etc/hosts") == ("/etc/hosts",)


def test_still_extracts_cat_redirect_and_git_add():
    batch = "cat > main.py\ngit add main.py utils.py"
    assert _changed_files_from_commands(batch) == ("main.py", "utils.py")


def test_paths_normalize_so_the_same_file_is_one_cell():
    batch = "cat > ./main.py\ngit add main.py"
    assert _changed_files_from_commands(batch) == ("main.py",)


def test_unbalanced_quotes_do_not_raise():
    assert _changed_files_from_commands("sed -i 's/a/b/ broken.py") == ()


def test_every_recognized_edit_form_can_name_its_target():
    """Guards the invariant the bug broke: detection and extraction agree."""
    for cmd in (
        "cat > f.py",
        "sed -i 's/a/b/' f.py",
        "tee f.py",
    ):
        assert _looks_like_file_edit(cmd), cmd
        assert _changed_files_from_commands(cmd) == ("f.py",), cmd
