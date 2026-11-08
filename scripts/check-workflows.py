#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Validate every GitHub Actions workflow file before it is pushed.

GitHub does not run a workflow whose YAML fails to parse. Instead it reports a
failed run with zero jobs and the event that pushed the broken file, which is
easy to misread as a job failure. The run then blocks the `workflow_run`
chain, so a broken workflow file can silently stop the daily build and release.

The failure mode worth calling out: a `run: |` block scalar ends at the first
line that is not indented deeper than the block. A heredoc body written at
column 0 therefore terminates the scalar and turns the rest of the script into
new top-level keys. Write such bodies with `echo` inside braces instead, or
indent them and strip the indentation explicitly.

Usage:
    scripts/check-workflows.py                 # check .github/workflows/*.yml
    scripts/check-workflows.py path/to/*.yml
    scripts/check-workflows.py --json

Exit status: 0 when every file parses and has at least one job, 1 otherwise,
2 on a usage or I/O error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a workflow bug
    print("error: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)


def check(path: Path) -> dict:
    """Return a result dict for one workflow file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"file": str(path), "ok": False, "error": f"cannot read: {exc}"}

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # Trim PyYAML's multi-line report to the first two lines; the rest is
        # usually a caret diagram that does not help in a one-line summary.
        lines = [line for line in str(exc).splitlines() if line.strip()]
        return {
            "file": str(path),
            "ok": False,
            "error": " | ".join(lines[:3]),
        }

    if not isinstance(data, dict):
        return {"file": str(path), "ok": False, "error": "top level is not a mapping"}

    # PyYAML resolves the bare `on:` key to boolean True under YAML 1.1.
    # GitHub reads the file as YAML 1.2 and sees the string "on".
    triggers = data.get("on", data.get(True))
    if triggers is None:
        return {"file": str(path), "ok": False, "error": "no 'on:' trigger block"}

    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return {"file": str(path), "ok": False, "error": "no jobs defined"}

    return {
        "file": str(path),
        "ok": True,
        "triggers": sorted(triggers) if isinstance(triggers, dict) else [str(triggers)],
        "jobs": sorted(jobs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="workflow files (default: .github/workflows/*.yml and *.yaml)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    if args.paths:
        targets = args.paths
    else:
        root = Path(__file__).resolve().parent.parent
        directory = root / ".github/workflows"
        if not directory.is_dir():
            print(f"error: {directory} not found", file=sys.stderr)
            return 2
        targets = sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml")))

    if not targets:
        print("error: no workflow files found", file=sys.stderr)
        return 2

    results = [check(path) for path in targets]
    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"ok": not failed, "workflows": results}, indent=2))
        return 0 if not failed else 1

    for result in results:
        name = result["file"]
        if result["ok"]:
            print(f"[OK  ] {name}")
            print(f"       triggers: {', '.join(result['triggers'])}")
            print(f"       jobs    : {', '.join(result['jobs'])}")
        else:
            print(f"[FAIL] {name}")
            print(f"       {result['error']}")

    print()
    if failed:
        print(f"{len(failed)} of {len(results)} workflow file(s) do not parse.")
        print("GitHub will not run them, and the workflow_run chain that drives")
        print("the daily build and release will stall. Fix before pushing.")
        return 1

    print(f"All {len(results)} workflow file(s) parse and define at least one job.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
