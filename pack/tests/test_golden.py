"""nimbus — golden-path knowledge tests (golden.py).

Own the pure knowledge contract: the name validator (incl. path-traversal
rejection), the 19-provider breadth, that the rendered files parse and that the
deploy-readiness REQUIRED_FILES are actually a subset of what scaffold writes (so
a fresh scaffold can never report a "missing" required file), and that the marker
payload is internally consistent.

Pure stdlib + pytest. No filesystem, no network — golden.py is pure.
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nimbus import golden  # noqa: E402


def test_valid_name_accepts_reasonable_names():
    for ok in ("app", "my-app", "my_app", "app.2", "a1"):
        assert golden.valid_name(ok), ok


def test_valid_name_rejects_traversal_and_junk():
    for bad in ("", "../evil", "a/b", ".hidden", "App", "has space", "-leads", "x" * 101):
        assert not golden.valid_name(bad), bad


def test_providers_are_19_unique_and_include_golden():
    assert len(golden.PROVIDERS) == 19
    assert len(set(golden.PROVIDERS)) == 19
    assert golden.GOLDEN_PROVIDER in golden.PROVIDERS


def test_golden_path_string():
    assert golden.golden_path() == "vite + voidzero + cloudflare + convex"


def test_stack_order_covers_every_layer():
    # golden_path() renders STACK in STACK_ORDER; if the order list ever drifts from
    # the stack it would silently drop (or KeyError on) a layer. Pin them together.
    assert set(golden.STACK_ORDER) == set(golden.STACK)
    rendered = golden.golden_path()
    for layer in golden.STACK.values():
        assert layer in rendered


def test_env_example_documents_the_required_creds():
    # The scaffolded app's .env.example must document exactly the deploy creds that
    # `nimbus readiness` asserts — otherwise a user has no pointer to what to set.
    env_example = golden.render_files("demo")[".env.example"]
    for var in golden.REQUIRED_ENV:
        assert var in env_example, var


def test_render_files_present_and_parseable():
    files = golden.render_files("demo")
    # name substitution happened (sentinel gone, name present)
    assert "__NAME__" not in files["index.html"]
    assert "demo" in files["index.html"]
    # package.json is valid JSON with the voidzero override + react/convex deps
    pkg = json.loads(files["package.json"])
    assert pkg["name"] == "demo"
    assert pkg["overrides"]["vite"].startswith("npm:rolldown-vite")
    assert {"convex", "react"} <= set(pkg["dependencies"])
    assert "vitest" in pkg["devDependencies"]  # voidzero test runner
    # tsconfig is valid JSON; the convex schema + react entry are present
    assert json.loads(files["tsconfig.json"])["compilerOptions"]["jsx"] == "react-jsx"
    assert "convex/schema.ts" in files
    assert "src/main.tsx" in files


def test_wrangler_uses_workers_static_assets():
    files = golden.render_files("demo")
    wr = files["wrangler.toml"]
    assert "[assets]" in wr and "single-page-application" in wr
    assert golden.COMPAT_DATE in wr


def test_required_files_are_subset_of_rendered():
    rendered = set(golden.render_files("demo"))
    assert set(golden.REQUIRED_FILES) <= rendered


def test_marker_payload_consistent():
    m = golden.marker_payload("demo")
    assert m["schema"] == golden.SCHEMA
    assert m["name"] == "demo"
    assert m["stack"] == golden.STACK
    assert m["requirements"]["files"] == list(golden.REQUIRED_FILES)
    assert m["requirements"]["env"] == list(golden.REQUIRED_ENV)
    assert m["requirements"]["tools"] == list(golden.REQUIRED_TOOLS)
