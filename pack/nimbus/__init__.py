"""nimbus — the cloud app-hosting enabler engine for a gas city.

A pure-stdlib toolkit that makes a gas city *app-hosting-capable*: it gives
agents a golden path for standing up and deploying a new web app
(vite + voidzero + cloudflare + convex) plus breadth across the 19 cloud
providers curated in this marketplace.

The app-scaffold + deploy-readiness engine landed in nim-rsa. The golden-path
hosting skill (nim-ulq), the 19 curated provider skills (nim-6y5), and the
launch-quality docs/tests (nim-114) follow. See ``docs/DESIGN.md``.

Public surface (what the CLI builds on):

- :mod:`nimbus.golden`    — the golden-path knowledge: the stack, the 19 curated
  providers, the file templates a scaffolded app gets, and the deploy-readiness
  requirements. Pure data + render helpers.
- :mod:`nimbus.scaffold`  — render the golden knowledge into a new project tree.
- :mod:`nimbus.readiness` — inspect a project dir + the environment and assess
  deploy-readiness.
- :mod:`nimbus.cli`       — the ``version`` / ``info`` / ``scaffold`` /
  ``readiness`` / ``providers`` command implementations the ``bin/nimbus``
  wrapper invokes via ``python -m nimbus.cli``.
"""

from __future__ import annotations

SCHEMA = "nimbus.v0"
__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__"]
