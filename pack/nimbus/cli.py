"""nimbus CLI — scaffold + deploy a web app on a gas city.

    nimbus version   [--json]                       print the pack version
    nimbus info      [--json]                       pack identity + capabilities
    nimbus scaffold  NAME [--dir DIR] [--force] [--json]
        scaffold a golden-path app (vite + voidzero + cloudflare + convex)
        into DIR/NAME.
    nimbus readiness [DIR] [--json]
        check a scaffolded app's deploy readiness (files + creds + toolchain).
    nimbus providers [name] [--json]
        list the 19 curated cloud providers behind the golden path, or one
        provider's curated skills.

``info``, ``providers`` and ``version`` are pure reads; ``readiness`` reads a
project dir + the environment; ``scaffold`` writes a project tree.

Exit codes: ``readiness`` returns 0 ready / 1 not-ready / 2 no-such-dir;
``scaffold`` returns 1 on a bad name or a clobbered target; ``providers``
returns 2 when the index is unavailable or the named provider is unknown;
everything else 0. Pure stdlib; invoked as ``python -m nimbus.cli`` by the
``bin/nimbus`` wrapper.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import nimbus
from nimbus import golden
from nimbus import readiness as R
from nimbus import scaffold as S

# The pack's provider-breadth index — generated from the marketplace's cloud-*
# plugins by `npm run regen:pack-providers` and carried inside the pack so the
# breadth stays reachable after the pack is vendored into a city. Lives next to
# this module (pack/nimbus/providers.json).
_PROVIDERS_PATH = Path(__file__).resolve().parent / "providers.json"

# The pack's build-out, threaded through `info` so the surface stays honest about
# what has landed vs. what is still deferred. Mirrors the way the cockpit pack
# threads bead ids (cockpit-1ll.*) through its surfaces.
#   (item, bead, landed)
ROADMAP = [
    ("golden-path hosting skill (vite+voidzero+cloudflare+convex)", "nim-ulq", True),
    ("bin/nimbus app scaffold + deploy engine (stdlib-only)", "nim-rsa", True),
    ("19 provider skills curated in + validator/regen wiring", "nim-6y5", True),
    ("docs/DESIGN.md + tests + README to launch quality", "nim-114", True),
]

COMMANDS = ["version", "info", "scaffold", "readiness", "providers"]


def _load_providers() -> Optional[dict[str, Any]]:
    try:
        with open(_PROVIDERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _match_provider(index: dict[str, Any], name: str) -> Optional[dict[str, Any]]:
    """Find a provider by name, accepting either 'aws' or 'cloud-aws'."""
    want = name.strip().lower()
    want_full = want if want.startswith("cloud-") else f"cloud-{want}"
    for p in index.get("providers", []):
        if want == p.get("name") or want_full == p.get("name") or want == p.get("prefix"):
            return p
    return None


def _one_line(text: str, width: int = 64) -> str:
    """The gist of a description: the lead-in before ' — ', clipped to width."""
    head = (text or "").split(" — ")[0].strip()
    return head if len(head) <= width else head[: width - 1] + "…"


def cmd_version(args: argparse.Namespace, out, err) -> int:
    if args.json:
        out.write(json.dumps({"name": "nimbus", "version": nimbus.__version__}) + "\n")
    else:
        out.write(f"nimbus {nimbus.__version__}\n")
    return 0


def cmd_info(args: argparse.Namespace, out, err) -> int:
    info = {
        "name": "nimbus",
        "version": nimbus.__version__,
        "schema": nimbus.SCHEMA,
        "status": "active",
        "golden_path": dict(golden.STACK),
        "providers": len(golden.PROVIDERS),
        "commands": COMMANDS,
        "roadmap": [
            {"item": item, "bead": bead, "landed": landed} for item, bead, landed in ROADMAP
        ],
    }
    if args.json:
        out.write(json.dumps(info, indent=2) + "\n")
        return 0
    out.write(f"nimbus {nimbus.__version__}  (schema {nimbus.SCHEMA})\n")
    out.write(f"golden path: {golden.golden_path()}\n")
    out.write(f"providers:   {len(golden.PROVIDERS)} clouds (the breadth escape hatch)\n")
    out.write(f"commands:    {', '.join(COMMANDS)}\n")
    if ROADMAP:
        out.write("\nRoadmap:\n")
        for item, bead, landed in ROADMAP:
            mark = "x" if landed else " "
            out.write(f"  [{mark}] {item}  [{bead}]\n")
    return 0


def cmd_scaffold(args: argparse.Namespace, out, err) -> int:
    try:
        result = S.scaffold_app(args.name, args.dir, force=args.force)
    except S.ScaffoldError as e:
        err.write(f"nimbus scaffold: {e}\n")
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


def cmd_readiness(args: argparse.Namespace, out, err) -> int:
    verdict = R.check_readiness(args.dir)
    if args.json:
        out.write(json.dumps(verdict, indent=2) + "\n")
    else:
        _render_readiness_text(verdict, out)
    if not verdict["exists"]:
        return 2
    return 0 if verdict["ready"] else 1


def cmd_providers(args: argparse.Namespace, out, err) -> int:
    index = _load_providers()
    if index is None:
        err.write(
            "nimbus: provider index unavailable — run 'npm run regen:pack-providers' "
            "in the marketplace repo to (re)generate pack/nimbus/providers.json.\n"
        )
        return 2
    providers = index.get("providers", [])

    # One provider: show its skills.
    if args.name:
        p = _match_provider(index, args.name)
        if p is None:
            known = ", ".join(pp.get("name", "?") for pp in providers)
            err.write(f"nimbus: unknown provider '{args.name}'. Known providers: {known}\n")
            return 2
        if args.json:
            out.write(json.dumps(p, indent=2) + "\n")
            return 0
        out.write(f"{p['name']}  (v{p.get('version', '?')})  —  {p.get('skill_count', 0)} skills\n")
        out.write(f"{p.get('description', '')}\n\n")
        for s in p.get("skills", []):
            out.write(f"  {s.get('slug', ''):<32}  {_one_line(s.get('description', ''), 96)}\n")
        return 0

    # All providers: the breadth list.
    if args.json:
        out.write(json.dumps(index, indent=2) + "\n")
        return 0
    gp = index.get("golden_path", {})
    stack = " + ".join(v for v in (gp.get("build"), gp.get("backend"), gp.get("hosting")) if v)
    out.write(f"nimbus providers — {len(providers)} clouds behind the golden path ({stack})\n\n")
    for p in providers:
        out.write(f"  {p.get('name', ''):<20} {p.get('skill_count', 0):>2} skills  {_one_line(p.get('description', ''))}\n")
    out.write(
        f"\nThe golden path hosts on {gp.get('hosting', 'cloudflare')}; reach for another "
        "cloud's skills when it doesn't fit.\n"
        "Run 'nimbus providers <name>' for one provider's skills, or add '--json'.\n"
    )
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
        "providers",
        help="list the 19 clouds behind the golden path, or one provider's skills",
    )
    pp.add_argument("name", nargs="?", help="a provider (e.g. 'aws' or 'cloud-aws') to show its skills")
    pp.add_argument("--json", action="store_true", help="emit JSON")
    pp.set_defaults(func=cmd_providers)

    return p


def main(argv: Optional[Sequence[str]] = None, out=None, err=None) -> int:
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        # Bare invocation (no subcommand): print help instead of erroring, so the
        # CLI is discoverable.
        parser.print_help(out)
        return 0
    return int(func(args, out, err))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
