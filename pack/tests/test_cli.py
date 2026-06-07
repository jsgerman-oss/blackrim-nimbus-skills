"""nimbus — CLI surface tests (version / info / scaffold / readiness / providers).

Own the CLI contract and its exit-code state machine: ``readiness`` returns
0 / 1 / 2 for ready / not-ready / no-such-dir; ``scaffold`` writes a tree and
returns 1 on a bad name or a clobbered target; ``version`` / ``info`` /
``providers`` render both text and JSON; a bare invocation prints help instead of
erroring. No network — ``scaffold`` writes under tmp_path and ``readiness`` is fed
an injected env + ``which`` via monkeypatch so it never depends on real secrets or
PATH.

Pure stdlib + pytest. The pack root is importable so ``nimbus.cli.main`` resolves.
The fixture-free subset also runs standalone via ``python3 tests/test_cli.py``.
"""

from __future__ import annotations

import inspect
import io
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nimbus import cli  # noqa: E402


def run(argv):
    out = io.StringIO()
    rc = cli.main(argv, out=out)
    return rc, out.getvalue()


def run_err(argv):
    out, err = io.StringIO(), io.StringIO()
    rc = cli.main(argv, out=out, err=err)
    return rc, out.getvalue(), err.getvalue()


# ---- version --------------------------------------------------------------- #

def test_version_text():
    rc, s = run(["version"])
    assert rc == 0
    assert s.startswith("nimbus ")


def test_version_json():
    rc, s = run(["version", "--json"])
    assert rc == 0
    assert json.loads(s)["name"] == "nimbus"


# ---- info ------------------------------------------------------------------ #

def test_info_text_shows_golden_path():
    rc, s = run(["info"])
    assert rc == 0
    assert "golden path: vite + voidzero + cloudflare + convex" in s


def test_info_text_shows_providers_and_roadmap():
    rc, s = run(["info"])
    assert rc == 0
    assert "providers:   19 clouds" in s
    assert "Roadmap:" in s
    assert "nim-6y5" in s  # the provider-curation bead is named in the roadmap


def test_info_json_active_with_roadmap():
    rc, s = run(["info", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["status"] == "active"
    assert data["providers"] == 19
    assert "scaffold" in data["commands"] and "readiness" in data["commands"]
    assert isinstance(data["roadmap"], list) and data["roadmap"]


# ---- scaffold -------------------------------------------------------------- #

def test_scaffold_writes_tree(tmp_path):
    rc, s = run(["scaffold", "myapp", "--dir", str(tmp_path)])
    assert rc == 0
    root = tmp_path / "myapp"
    assert (root / "package.json").is_file()
    assert (root / "wrangler.toml").is_file()
    assert (root / "convex" / "schema.ts").is_file()
    assert (root / "src" / "main.tsx").is_file()
    marker = json.loads((root / ".nimbus.json").read_text())
    assert marker["stack"]["hosting"] == "cloudflare"


def test_scaffold_json_reports_files(tmp_path):
    rc, s = run(["scaffold", "myapp", "--dir", str(tmp_path), "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["root"].endswith("myapp")
    assert "package.json" in data["files"]


def test_scaffold_refuses_clobber_then_force(tmp_path):
    target = tmp_path / "myapp"
    target.mkdir()
    (target / "keep.txt").write_text("mine")
    rc, _ = run(["scaffold", "myapp", "--dir", str(tmp_path)])
    assert rc == 1  # non-empty target, no --force
    assert (target / "keep.txt").read_text() == "mine"  # untouched
    rc, _ = run(["scaffold", "myapp", "--dir", str(tmp_path), "--force"])
    assert rc == 0
    assert (target / "package.json").is_file()


def test_scaffold_bad_name_returns_1():
    # Invalid name is rejected before any filesystem write (also a path-traversal
    # guard: '../evil' must never escape the parent dir).
    rc, _ = run(["scaffold", "../evil"])
    assert rc == 1


# ---- readiness ------------------------------------------------------------- #

def _make_ready(monkeypatch):
    """Set the deploy creds + a fake `which` so readiness can reach DEPLOY-READY."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CONVEX_DEPLOY_KEY", "key")
    monkeypatch.setattr("shutil.which", lambda t: "/usr/bin/" + t)


def test_readiness_ready(tmp_path, monkeypatch):
    run(["scaffold", "myapp", "--dir", str(tmp_path)])
    _make_ready(monkeypatch)
    rc, s = run(["readiness", str(tmp_path / "myapp")])
    assert rc == 0
    assert "DEPLOY-READY" in s


def test_readiness_not_ready_missing_env(tmp_path, monkeypatch):
    run(["scaffold", "myapp", "--dir", str(tmp_path)])
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CONVEX_DEPLOY_KEY", raising=False)
    rc, s = run(["readiness", str(tmp_path / "myapp")])
    assert rc == 1
    assert "MISSING" in s


def test_readiness_json(tmp_path, monkeypatch):
    run(["scaffold", "myapp", "--dir", str(tmp_path)])
    _make_ready(monkeypatch)
    rc, s = run(["readiness", str(tmp_path / "myapp"), "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["ready"] is True
    assert data["is_nimbus_app"] is True


def test_readiness_missing_dir_returns_2():
    nodir = os.path.join(tempfile.gettempdir(), "nimbus-does-not-exist-zzz")
    rc, s = run(["readiness", nodir])
    assert rc == 2
    assert "NO SUCH DIRECTORY" in s


# ---- bare ------------------------------------------------------------------ #

def test_bare_invocation_prints_help_not_error():
    rc, s = run([])
    assert rc == 0
    assert "usage:" in s.lower()


# --- providers: the breadth behind the golden path (nim-6y5) --------------

def test_providers_list_text_shows_all_clouds():
    rc, s = run(["providers"])
    assert rc == 0
    assert "19 clouds" in s
    assert "cloud-aws" in s and "cloud-cloudflare" in s and "cloud-vultr" in s


def test_providers_list_json_is_the_index():
    rc, s = run(["providers", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["schema"] == "nimbus.providers.v1"
    assert data["provider_count"] == len(data["providers"]) == 19
    assert data["golden_path"]["hosting"] == "cloudflare"


def test_providers_detail_by_prefix_lists_skills():
    rc, s = run(["providers", "aws"])
    assert rc == 0
    assert "cloud-aws" in s
    assert "aws-compute" in s  # a provider skill is reachable through the pack


def test_providers_detail_accepts_full_name():
    rc, s = run(["providers", "cloud-aws"])
    assert rc == 0
    assert "aws-" in s


def test_providers_unknown_errors_on_stderr():
    rc, out, err = run_err(["providers", "nope"])
    assert rc == 2
    assert out == ""
    assert "unknown provider" in err.lower()


def test_providers_index_is_well_formed():
    # The carried snapshot the pack ships: parses, is self-consistent, and every
    # provider exposes its prefixed skills so the golden path's breadth is reachable.
    with open(cli._PROVIDERS_PATH, encoding="utf-8") as f:
        index = json.load(f)
    assert index["provider_count"] == len(index["providers"]) == 19
    assert index["golden_path"]["primary_provider"].startswith("cloud-")
    for p in index["providers"]:
        assert p["name"].startswith("cloud-")
        assert isinstance(p["prefix"], str) and p["prefix"]
        assert p["skill_count"] == len(p["skills"]) >= 5
        for skill in p["skills"]:
            assert skill["slug"].startswith(p["prefix"] + "-")


def test_info_marks_nim_6y5_landed():
    rc, s = run(["info", "--json"])
    assert rc == 0
    roadmap = json.loads(s)["roadmap"]
    entry = next(e for e in roadmap if e["bead"] == "nim-6y5")
    assert entry["landed"] is True


if __name__ == "__main__":  # allow running the fixture-free subset without pytest
    failures = skipped = 0
    for _name, _fn in sorted(globals().items()):
        if not (_name.startswith("test_") and callable(_fn)):
            continue
        if inspect.signature(_fn).parameters:  # needs tmp_path / monkeypatch
            skipped += 1
            print(f"skip {_name} (needs pytest fixtures)")
            continue
        try:
            _fn()
            print(f"ok   {_name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {_name}: {e}")
    print(f"\n{'PASS' if failures == 0 else 'FAIL'} — {failures} failure(s), {skipped} skipped")
    raise SystemExit(1 if failures else 0)
