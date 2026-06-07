"""nimbus — deploy-readiness tests (readiness.py).

Own the assess contract and its verdict shape: a complete scaffold with creds +
toolchain is ready; each missing dimension (file / env / tool) flips it not-ready
and is reported; a non-existent dir is exists=False with every requirement
"missing"; requirements are read data-driven from the ``.nimbus.json`` marker
when present, else from the golden defaults.

``env`` and ``which`` are injected so the suite is fully hermetic — it never reads
real secrets or PATH.
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nimbus import golden, readiness, scaffold  # noqa: E402

_FULL_ENV = {"CLOUDFLARE_API_TOKEN": "tok", "CONVEX_DEPLOY_KEY": "key"}


def _all_tools(_name):
    return "/usr/bin/" + _name


def _no_tools(_name):
    return None


def test_ready_when_complete(tmp_path):
    scaffold.scaffold_app("app", str(tmp_path))
    v = readiness.check_readiness(str(tmp_path / "app"), env=_FULL_ENV, which=_all_tools)
    assert v["ready"] is True
    assert v["is_nimbus_app"] is True
    assert v["stack"]["backend"] == "convex"
    assert v["missing_files"] == [] and v["missing_env"] == [] and v["missing_tools"] == []


def test_missing_env_blocks(tmp_path):
    scaffold.scaffold_app("app", str(tmp_path))
    v = readiness.check_readiness(str(tmp_path / "app"), env={}, which=_all_tools)
    assert v["ready"] is False
    assert set(v["missing_env"]) == set(golden.REQUIRED_ENV)


def test_missing_tools_blocks(tmp_path):
    scaffold.scaffold_app("app", str(tmp_path))
    v = readiness.check_readiness(str(tmp_path / "app"), env=_FULL_ENV, which=_no_tools)
    assert v["ready"] is False
    assert set(v["missing_tools"]) == set(golden.REQUIRED_TOOLS)


def test_missing_file_blocks(tmp_path):
    scaffold.scaffold_app("app", str(tmp_path))
    (tmp_path / "app" / "wrangler.toml").unlink()
    v = readiness.check_readiness(str(tmp_path / "app"), env=_FULL_ENV, which=_all_tools)
    assert v["ready"] is False
    assert v["missing_files"] == ["wrangler.toml"]


def test_nonexistent_dir(tmp_path):
    v = readiness.check_readiness(str(tmp_path / "nope"), env=_FULL_ENV, which=_all_tools)
    assert v["exists"] is False
    assert v["is_nimbus_app"] is False
    assert set(v["missing_files"]) == set(golden.REQUIRED_FILES)


def test_no_marker_falls_back_to_golden_defaults(tmp_path):
    # A bare dir with all required files but no .nimbus.json marker: not recognized
    # as a nimbus app, but still checked against the golden defaults.
    proj = tmp_path / "bare"
    proj.mkdir()
    for f in golden.REQUIRED_FILES:
        p = proj / f
        p.parent.mkdir(parents=True, exist_ok=True)  # e.g. convex/schema.ts
        p.write_text("x")
    v = readiness.check_readiness(str(proj), env=_FULL_ENV, which=_all_tools)
    assert v["is_nimbus_app"] is False
    assert v["missing_files"] == []
    assert v["ready"] is True


def test_malformed_marker_is_ignored(tmp_path):
    # A corrupt .nimbus.json must not crash the check: read_marker swallows the
    # decode error, the dir is treated as not-a-nimbus-app, and requirements fall
    # back to the golden defaults.
    proj = tmp_path / "broken"
    proj.mkdir()
    (proj / readiness.MARKER).write_text("{ this is not json")
    assert readiness.read_marker(str(proj)) is None
    v = readiness.check_readiness(str(proj), env=_FULL_ENV, which=_all_tools)
    assert v["is_nimbus_app"] is False
    assert set(v["missing_files"]) == set(golden.REQUIRED_FILES)  # golden defaults


def test_non_object_marker_is_ignored(tmp_path):
    # Valid JSON but not an object (e.g. a list) is also rejected — read_marker only
    # accepts a dict.
    proj = tmp_path / "listmarker"
    proj.mkdir()
    (proj / readiness.MARKER).write_text("[1, 2, 3]")
    assert readiness.read_marker(str(proj)) is None


def test_marker_requirements_are_authoritative(tmp_path):
    # A marker that declares a custom required file drives the check (data-driven).
    proj = tmp_path / "custom"
    proj.mkdir()
    marker = {
        "schema": golden.SCHEMA,
        "requirements": {"files": ["only-this.txt"], "env": [], "tools": []},
    }
    (proj / readiness.MARKER).write_text(json.dumps(marker))
    v = readiness.check_readiness(str(proj), env={}, which=_no_tools)
    assert v["missing_files"] == ["only-this.txt"]
    assert v["missing_env"] == [] and v["missing_tools"] == []
    (proj / "only-this.txt").write_text("x")
    v2 = readiness.check_readiness(str(proj), env={}, which=_no_tools)
    assert v2["ready"] is True  # custom marker required nothing else
