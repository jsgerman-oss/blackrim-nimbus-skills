"""nimbus — scaffold writer tests (scaffold.py).

Own the write contract: a fresh scaffold lays down the full golden-path tree plus
the ``.nimbus.json`` marker, an invalid name raises before touching the disk, a
non-empty target is refused unless ``force=True``, and ``force`` overlays without
clobbering unrelated files.

Pure stdlib + pytest; writes go under tmp_path so nothing escapes the test.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nimbus import golden, scaffold  # noqa: E402


def test_scaffold_writes_full_tree(tmp_path):
    result = scaffold.scaffold_app("myapp", str(tmp_path))
    root = tmp_path / "myapp"
    assert result["root"] == str(root)
    # every rendered file + the marker exists on disk
    expected = set(golden.render_files("myapp")) | {scaffold.MARKER}
    assert set(result["files"]) == expected
    for rel in expected:
        assert (root / rel).is_file(), rel
    marker = json.loads((root / scaffold.MARKER).read_text())
    assert marker["kind"] == "nimbus-golden-path-app"
    assert marker["name"] == "myapp"


def test_scaffold_rejects_bad_name(tmp_path):
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold_app("../evil", str(tmp_path))
    # nothing written
    assert not (tmp_path / "evil").exists()
    assert list(tmp_path.iterdir()) == []


def test_scaffold_refuses_nonempty_target(tmp_path):
    target = tmp_path / "myapp"
    target.mkdir()
    (target / "keep.txt").write_text("mine")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold_app("myapp", str(tmp_path))
    assert (target / "keep.txt").read_text() == "mine"


def test_scaffold_force_overlays(tmp_path):
    target = tmp_path / "myapp"
    target.mkdir()
    (target / "keep.txt").write_text("mine")
    result = scaffold.scaffold_app("myapp", str(tmp_path), force=True)
    assert (target / "package.json").is_file()
    assert (target / "keep.txt").read_text() == "mine"  # unrelated file preserved
    assert "package.json" in result["files"]


def test_scaffold_into_empty_existing_dir(tmp_path):
    target = tmp_path / "myapp"
    target.mkdir()  # exists but empty -> allowed without force
    result = scaffold.scaffold_app("myapp", str(tmp_path))
    assert (target / "wrangler.toml").is_file()
    assert result["name"] == "myapp"
