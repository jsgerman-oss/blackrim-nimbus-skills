"""nimbus CLI — scaffold + deploy a web app on a gas city.

    nimbus version  [--json]   print the pack version
    nimbus info     [--json]   print the pack identity + the scaffold's roadmap

SCAFFOLD (nim-bam): this CLI is a stub. The real surface — scaffold a new app on
the golden path (vite + voidzero + cloudflare + convex) and deploy it to one of
19 cloud providers — lands in nim-rsa. The commands here exist only to prove the
``bin/nimbus`` -> ``python -m nimbus.cli`` wiring and to give the smoke test
something to assert. Pure stdlib; invoked as ``python -m nimbus.cli`` by the
``bin/nimbus`` wrapper.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

import nimbus

# Where the deferred surface lands — kept here so `info` stays honest about the
# scaffold and points at the follow-up beads that fill it in. Mirrors the way the
# cockpit pack threads bead ids (cockpit-1ll.*) through its surfaces.
ROADMAP = [
    ("bin/nimbus app scaffold + deploy helpers (stdlib-only)", "nim-rsa"),
    ("golden-path hosting skill (vite+voidzero+cloudflare+convex)", "nim-ulq"),
    ("19 provider skills curated in + validator/regen wiring", "nim-6y5"),
    ("docs/DESIGN.md + tests + README to launch quality", "nim-114"),
]


def cmd_version(args: argparse.Namespace, out) -> int:
    if args.json:
        out.write(json.dumps({"name": "nimbus", "version": nimbus.__version__}) + "\n")
    else:
        out.write(f"nimbus {nimbus.__version__}\n")
    return 0


def cmd_info(args: argparse.Namespace, out) -> int:
    info = {
        "name": "nimbus",
        "version": nimbus.__version__,
        "schema": nimbus.SCHEMA,
        "status": "scaffold",
        "roadmap": [{"item": item, "bead": bead} for item, bead in ROADMAP],
    }
    if args.json:
        out.write(json.dumps(info, indent=2) + "\n")
        return 0
    out.write(f"nimbus {nimbus.__version__}  (schema {nimbus.SCHEMA})\n")
    out.write("status: SCAFFOLD — structure + manifests only (nim-bam).\n\n")
    out.write("Deferred surface (lands in follow-up beads):\n")
    for item, bead in ROADMAP:
        out.write(f"  - {item}  [{bead}]\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nimbus",
        description="Scaffold + deploy a web app on a gas city (golden path + 19 clouds).",
    )
    p.add_argument("--version", action="version", version=f"nimbus {nimbus.__version__}")
    sub = p.add_subparsers(dest="cmd")

    pv = sub.add_parser("version", help="print the pack version")
    pv.add_argument("--json", action="store_true", help="emit JSON")
    pv.set_defaults(func=cmd_version)

    pi = sub.add_parser("info", help="print the pack identity + the scaffold's roadmap")
    pi.add_argument("--json", action="store_true", help="emit JSON")
    pi.set_defaults(func=cmd_info)

    return p


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        # Bare invocation (no subcommand): print help instead of erroring, so the
        # scaffold CLI is discoverable. Real subcommands land in nim-rsa.
        parser.print_help(out)
        return 0
    return int(func(args, out))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
