"""Tests for the storage layout path derivation (doc 29 §5, doc 25 §4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from turkish_code.depo.yerlesim import StorageLayout


def _layout() -> StorageLayout:
    return StorageLayout(data_dir=Path("/data/tc"))


def test_app_db_is_directly_under_data_dir() -> None:
    assert _layout().app_db_path == Path("/data/tc/app.db")


def test_workspace_paths_are_isolated_under_alanlar() -> None:
    layout = _layout()
    ws = "a1b2c3"
    assert layout.workspace_dir(ws) == Path("/data/tc/alanlar/a1b2c3")
    assert layout.workspace_db_path(ws) == Path("/data/tc/alanlar/a1b2c3/workspace.db")
    assert layout.blobs_dir(ws) == Path("/data/tc/alanlar/a1b2c3/blobs")
    assert layout.journal_dir(ws) == Path("/data/tc/alanlar/a1b2c3/journal")


def test_two_workspaces_get_physically_separate_dirs() -> None:
    layout = _layout()
    assert layout.workspace_dir("ws1") != layout.workspace_dir("ws2")


def test_layout_composes_under_a_data_dir_with_spaces() -> None:
    # The dev repo root is literally "Turkish Code" — spaced paths must be safe.
    layout = StorageLayout(data_dir=Path("/home/user/Turkish Code/data"))
    assert layout.app_db_path == Path("/home/user/Turkish Code/data/app.db")


@pytest.mark.parametrize(
    "bad_id",
    ["", "../escape", "a/b", "..", "with space", "semi;colon", "slash\\back"],
)
def test_unsafe_workspace_ids_are_rejected(bad_id: str) -> None:
    with pytest.raises(ValueError):
        _layout().workspace_dir(bad_id)


def test_safe_hex_like_ids_are_accepted() -> None:
    layout = _layout()
    for ok in ["deadbeef", "ABC-123_def", "0"]:
        assert layout.workspace_dir(ok).name == ok
