"""nimbus — the cloud app-hosting enabler engine for a gas city.

A pure-stdlib toolkit that makes a gas city *app-hosting-capable*: it gives
agents a golden path for standing up and deploying a new web app
(vite + voidzero + cloudflare + convex) plus breadth across the 19 cloud
providers curated in this marketplace.

STATUS: v1 SCAFFOLD (nim-bam). This module is a stub — the app-scaffold and
deploy engine lands in nim-rsa. See ``docs/DESIGN.md``.

Public surface (once the engine lands):

- :mod:`nimbus.cli` — the command implementations the ``bin/nimbus`` wrapper
  invokes via ``python -m nimbus.cli``.
"""

from __future__ import annotations

SCHEMA = "nimbus.v0"
__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__"]
