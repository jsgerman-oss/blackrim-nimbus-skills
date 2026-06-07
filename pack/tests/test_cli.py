"""nimbus — CLI smoke tests (scaffold).

Own the thin scaffold CLI contract: `version` and `info` render both text and
JSON, and a bare invocation prints help instead of erroring. There is no network
and no feature surface yet (that lands in nim-rsa), so these are pure, hermetic
smoke checks — just enough to prove the `bin/nimbus` -> `python -m nimbus.cli`
wiring resolves and the scaffold imports cleanly.

Pure stdlib + pytest. The pack root is importable so `nimbus.cli.main` resolves.
Runs under pytest, or standalone via `python3 tests/test_cli.py`.
"""

from __future__ import annotations

import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nimbus import cli  # noqa: E402


def run(argv):
    out = io.StringIO()
    rc = cli.main(argv, out=out)
    return rc, out.getvalue()


def test_version_text():
    rc, s = run(["version"])
    assert rc == 0
    assert s.startswith("nimbus ")


def test_version_json():
    rc, s = run(["version", "--json"])
    assert rc == 0
    assert json.loads(s)["name"] == "nimbus"


def test_info_text_flags_scaffold():
    rc, s = run(["info"])
    assert rc == 0
    assert "SCAFFOLD" in s


def test_info_json_has_roadmap():
    rc, s = run(["info", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["status"] == "scaffold"
    assert isinstance(data["roadmap"], list) and data["roadmap"]


def test_bare_invocation_prints_help_not_error():
    rc, s = run([])
    assert rc == 0
    assert "usage:" in s.lower()


if __name__ == "__main__":  # allow running without pytest
    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"ok   {_name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {_name}: {e}")
    print(f"\n{'PASS' if failures == 0 else 'FAIL'} — {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
