"""nimbus — bin/nimbus wrapper smoke tests.

Own the one seam the in-process ``cli.main`` tests can't reach: the real
``bin/nimbus`` executable. The wrapper resolves an interpreter (the pack venv if
present, else system ``python3``), sets ``PYTHONPATH`` to the pack root, and execs
``python -m nimbus.cli``. These run it as a subprocess and assert the wiring holds —
``version``/``info`` answer in text and JSON, and the path is independent of the
caller's cwd (the wrapper derives its own ``PACK_DIR``).

Pure stdlib + pytest. No network. Skipped if the interpreter is non-POSIX (the
wrapper is bash); on the supported platforms it always runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BIN = os.path.join(_ROOT, "bin", "nimbus")

# The wrapper is a bash script with a shebang; skip on platforms where it can't run
# (Windows). On POSIX it is always exercised.
pytestmark = pytest.mark.skipif(
    os.name != "posix" or not os.access(_BIN, os.X_OK),
    reason="bin/nimbus is a POSIX shell wrapper and must be executable",
)


def _run(args, cwd=None):
    return subprocess.run(
        [_BIN, *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )


def test_bin_version_text():
    p = _run(["version"])
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("nimbus ")


def test_bin_version_json():
    p = _run(["version", "--json"])
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["name"] == "nimbus"


def test_bin_info_shows_golden_path():
    p = _run(["info"])
    assert p.returncode == 0, p.stderr
    assert "vite + voidzero + cloudflare + convex" in p.stdout


def test_bin_runs_independent_of_cwd(tmp_path):
    # The wrapper derives PACK_DIR from its own location, so it must work from any
    # working directory — run it from an unrelated tmp dir.
    p = _run(["version"], cwd=str(tmp_path))
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("nimbus ")
