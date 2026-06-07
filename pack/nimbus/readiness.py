"""Assess whether a scaffolded project is deploy-ready against the golden-path
requirements — the read + assess side of the engine, analogous to cockpit's
``discovery.probe_api`` + ``assess_readiness`` but over a project directory and
the environment instead of an HTTP API.

A project is deploy-ready when it has the required files, the deploy-time
credentials are present in the environment, and the build/deploy toolchain is on
PATH. Requirements come from the app's ``.nimbus.json`` marker when present
(data-driven), else from :mod:`nimbus.golden` defaults.

Pure stdlib (``os`` + ``json`` + ``shutil``). No network.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Callable, Mapping, Optional

from nimbus import golden

MARKER = ".nimbus.json"


def read_marker(project_dir: str) -> Optional[dict[str, Any]]:
    """Read the ``.nimbus.json`` marker a scaffolded app carries, or ``None`` if
    it is absent or unreadable."""
    p = os.path.join(project_dir, MARKER)
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def _requirements(marker: Optional[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Requirements to check: from the marker if it carries a well-formed
    ``requirements`` table, else the :mod:`nimbus.golden` defaults."""
    req = marker.get("requirements") if isinstance(marker, Mapping) else None
    if isinstance(req, Mapping):
        return {
            "files": [str(x) for x in req.get("files", golden.REQUIRED_FILES)],
            "env": [str(x) for x in req.get("env", golden.REQUIRED_ENV)],
            "tools": [str(x) for x in req.get("tools", golden.REQUIRED_TOOLS)],
        }
    return {
        "files": list(golden.REQUIRED_FILES),
        "env": list(golden.REQUIRED_ENV),
        "tools": list(golden.REQUIRED_TOOLS),
    }


def check_readiness(
    project_dir: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> dict[str, Any]:
    """Assess deploy-readiness of ``project_dir``.

    ``env`` defaults to ``os.environ`` and ``which`` to ``shutil.which`` — both
    injectable so tests stay hermetic. Returns a verdict dict:

    - ``exists`` — the directory exists
    - ``is_nimbus_app`` — a ``.nimbus.json`` marker was found
    - ``stack`` — the marker's stack table (or ``None``)
    - ``missing_files`` / ``missing_env`` / ``missing_tools`` — unmet requirements
    - ``ready`` — exists and nothing missing
    """
    env = os.environ if env is None else env
    which = shutil.which if which is None else which

    exists = os.path.isdir(project_dir)
    marker = read_marker(project_dir) if exists else None
    req = _requirements(marker)

    missing_files = (
        [f for f in req["files"] if not os.path.isfile(os.path.join(project_dir, f))]
        if exists
        else list(req["files"])
    )
    missing_env = [k for k in req["env"] if not (env.get(k) or "").strip()]
    missing_tools = [t for t in req["tools"] if not which(t)]

    ready = exists and not missing_files and not missing_env and not missing_tools
    return {
        "project_dir": project_dir,
        "exists": exists,
        "is_nimbus_app": marker is not None,
        "stack": marker.get("stack") if marker else None,
        "missing_files": missing_files,
        "missing_env": missing_env,
        "missing_tools": missing_tools,
        "ready": ready,
    }
