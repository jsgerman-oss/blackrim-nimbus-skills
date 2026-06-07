"""Render the nimbus golden-path knowledge (:mod:`nimbus.golden`) into a new
project on disk — the write side of the engine, analogous to cockpit's
``discovery.write_descriptor`` but for a whole project tree.

Pure stdlib (``os`` + ``json``). No network.
"""

from __future__ import annotations

import json
import os
from typing import Any

from nimbus import golden

# The generated marker readiness reads back to recognize a nimbus app.
MARKER = ".nimbus.json"


class ScaffoldError(Exception):
    """Raised when a project cannot be scaffolded (bad name or target clobber)."""


def scaffold_app(name: str, parent_dir: str = ".", *, force: bool = False) -> dict[str, Any]:
    """Scaffold a golden-path app named ``name`` under ``parent_dir``/``name``.

    Returns ``{"name", "root", "files": [...]}`` (files sorted, relative to root).
    Raises :class:`ScaffoldError` on an invalid name, or when the target directory
    already exists and is non-empty (pass ``force=True`` to write into it anyway).

    Writes are not transactional: on an mid-write error a partial tree may remain.
    The pre-write target check keeps the common case (fresh dir) clean; ``force``
    intentionally overlays files onto whatever is already there.
    """
    if not golden.valid_name(name):
        raise ScaffoldError(
            f"invalid app name {name!r}: use lowercase letters, digits, '.', '-', '_' "
            "and start with a letter or digit"
        )
    root = os.path.join(parent_dir, name)
    if os.path.isdir(root) and os.listdir(root) and not force:
        raise ScaffoldError(
            f"target {root!r} exists and is not empty; pass force=True to write into it"
        )

    files = dict(golden.render_files(name))
    files[MARKER] = json.dumps(golden.marker_payload(name), indent=2) + "\n"

    written = []
    for rel, content in sorted(files.items()):
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)

    return {"name": name, "root": root, "files": written}
