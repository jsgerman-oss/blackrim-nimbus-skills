"""nimbus CLI — scaffold + deploy a web app on a gas city.

    nimbus version   [--json]                       print the pack version
    nimbus info      [--json]                       pack identity + capabilities
    nimbus scaffold  NAME [--dir DIR] [--force] [--json]
        scaffold a golden-path app (vite + voidzero + cloudflare + convex)
        into DIR/NAME.
    nimbus readiness [DIR] [--json]
        check a scaffolded app's deploy readiness (files + creds + toolchain).
    nimbus providers [--json]
        list the golden path + the 19 curated cloud providers (the breadth).

``info``, ``providers`` and ``version`` are pure reads; ``readiness`` reads a
project dir + the environment; ``scaffold`` writes a project tree.

Exit codes: ``readiness`` returns 0 ready / 1 not-ready / 2 no-such-dir;
``scaffold`` returns 1 on a bad name or a clobbered target; everything else 0.
Pure stdlib; invoked as ``python -m nimbus.cli`` by the ``bin/nimbus`` wrapper.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

import nimbus
from nimbus import golden
from nimbus import readiness as R
from nimbus import scaffold as S

# Remaining surface after this engine (nim-rsa) lands. Threaded through `info` so
# it stays honest about what is shipped vs. deferred — mirrors how the cockpit
# pack threads bead ids through its surfaces.
ROADMAP = [
    ("golden-path hosting skill (vite+voidzero+cloudflare+convex)", "nim-ulq"),
    ("19 provider skills curated in + validator/regen wiring", "nim-6y5"),
    ("docs/DESIGN.md + tests + README to launch quality", "nim-114"),
]

COMMANDS = ["version", "info", "scaffold", "readiness", "providers"]


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
        "status": "active",
        "golden_path": dict(golden.STACK),
        "providers": len(golden.PROVIDERS),
        "commands": COMMANDS,
        "roadmap": [{"item": item, "bead": bead} for item, bead in ROADMAP],
    }
    if args.json:
        out.write(json.dumps(info, indent=2) + "\n")
        return 0
    out.write(f"nimbus {nimbus.__version__}  (schema {nimbus.SCHEMA})\n")
    out.write(f"golden path: {golden.golden_path()}\n")
    out.write(f"providers:   {len(golden.PROVIDERS)} clouds (the breadth escape hatch)\n")
    out.write(f"commands:    {', '.join(COMMANDS)}\n")
    if ROADMAP:
        out.write("\nRemaining roadmap:\n")
        for item, bead in ROADMAP:
            out.write(f"  - {item}  [{bead}]\n")
    return 0


def cmd_scaffold(args: argparse.Namespace, out) -> int:
    try:
        result = S.scaffold_app(args.name, args.dir, force=args.force)
    except S.ScaffoldError as e:
        sys.stderr.write(f"nimbus scaffold: {e}\n")
        return 1
    if args.json:
        out.write(json.dumps(result, indent=2) + "\n")
        return 0
    out.write(f"scaffolded {result['name']} ({golden.golden_path()}) -> {result['root']}\n")
    out.write(f"  {len(result['files'])} files: {', '.join(result['files'])}\n")
    out.write("\nnext:\n")
    out.write(f"  cd {result['root']} && npm install && npx convex dev\n")
    out.write(f"  nimbus readiness {result['root']}   # check before deploy\n")
    return 0


def _render_readiness_text(v: dict, out) -> None:
    def line(label: str, value: str) -> None:
        out.write(f"{label + ':':<12}{value}\n")

    line("project", v["project_dir"])
    if not v["exists"]:
        line("status", "NO SUCH DIRECTORY")
        return
    line("nimbus app", "yes" if v["is_nimbus_app"] else "no (.nimbus.json marker missing)")
    for label, key in (("files", "missing_files"), ("env", "missing_env"), ("tools", "missing_tools")):
        miss = v[key]
        line(label, f"MISSING {len(miss)}: {', '.join(miss)}" if miss else "ok")
    out.write("\n" + ("DEPLOY-READY\n" if v["ready"] else "NOT deploy-ready (see above)\n"))


def cmd_readiness(args: argparse.Namespace, out) -> int:
    verdict = R.check_readiness(args.dir)
    if args.json:
        out.write(json.dumps(verdict, indent=2) + "\n")
    else:
        _render_readiness_text(verdict, out)
    if not verdict["exists"]:
        return 2
    return 0 if verdict["ready"] else 1


def cmd_providers(args: argparse.Namespace, out) -> int:
    if args.json:
        out.write(
            json.dumps(
                {
                    "golden_path": dict(golden.STACK),
                    "golden_provider": golden.GOLDEN_PROVIDER,
                    "providers": list(golden.PROVIDERS),
                },
                indent=2,
            )
            + "\n"
        )
        return 0
    out.write(f"golden path: {golden.golden_path()}\n")
    out.write(f"\n{len(golden.PROVIDERS)} providers (breadth; * = golden path):\n")
    for p in golden.PROVIDERS:
        mark = "  * " if p == golden.GOLDEN_PROVIDER else "    "
        out.write(f"{mark}{p}\n")
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

    pi = sub.add_parser("info", help="print the pack identity + capabilities")
    pi.add_argument("--json", action="store_true", help="emit JSON")
    pi.set_defaults(func=cmd_info)

    ps = sub.add_parser(
        "scaffold", help="scaffold a golden-path app (vite+voidzero+cloudflare+convex)"
    )
    ps.add_argument("name", help="app name (lowercase; becomes the new directory)")
    ps.add_argument("--dir", default=".", help="parent directory to create the app in (default: cwd)")
    ps.add_argument("--force", action="store_true", help="write into the target dir even if non-empty")
    ps.add_argument("--json", action="store_true", help="emit JSON")
    ps.set_defaults(func=cmd_scaffold)

    pr = sub.add_parser("readiness", help="check a golden-path app's deploy readiness")
    pr.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    pr.add_argument("--json", action="store_true", help="emit JSON")
    pr.set_defaults(func=cmd_readiness)

    pp = sub.add_parser(
        "providers", help="list the golden path + the 19 curated cloud providers"
    )
    pp.add_argument("--json", action="store_true", help="emit JSON")
    pp.set_defaults(func=cmd_providers)

    return p


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        # Bare invocation (no subcommand): print help instead of erroring, so the
        # CLI is discoverable.
        parser.print_help(out)
        return 0
    return int(func(args, out))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
