#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Verify that the built kernel still matches the frozen GKI ABI.

Why this exists
---------------
GKI freezes the layout of every struct and union that crosses the kernel /
vendor-module boundary.  ``android/abi_gki_aarch64.stg`` records that frozen
contract: for each type it stores the exact ``bytesize`` and the list of member
ids.

Closed-source vendor modules are compiled against that frozen layout.  If a
build changes the size of a type, every module that touches it reads and writes
fields at the wrong offsets.  The kernel will *not* stop them: this
configuration sets ``CONFIG_MODULE_FORCE_LOAD=y``, so ``try_to_force_load()``
returns success and the module loads anyway, tainting the kernel and then
corrupting memory.  The usual symptom is a hang at the boot logo.

The trap this guards against is that a **Kconfig option** can silently change
struct layout.  ``CONFIG_READ_ONLY_THP_FOR_FS=y`` looks like a harmless
feature toggle but adds ``atomic_t nr_thps`` to ``struct address_space``,
turning the frozen 240-byte layout into 244 bytes.  That bricked a device once;
never again.

The frozen `.stg` snapshot is not always in sync with a given tree (for
example `lib/zstd` here diverges from the snapshot by thousands of lines, so
three `ZSTD_*` types legitimately differ).  For that reason the primary check
compares against a **baseline recorded from a build that was verified to boot**.
Only differences introduced since that baseline are reported.

Usage:
    scripts/abi-guard.py --write-baseline    # record the current build
    scripts/abi-guard.py                     # compare against the baseline
    scripts/abi-guard.py --stg               # compare against the frozen snapshot
    scripts/abi-guard.py --json
    scripts/abi-guard.py --list-changed      # only show differences

Exit status: 0 when every ABI type still has its frozen size, 1 when a size
changed, 2 on a usage or I/O error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

NAME_RE = re.compile(r'^\s*name:\s*"([^"]+)"\s*$')
SIZE_RE = re.compile(r"^\s*bytesize:\s*(\d+)\s*$")
BLOCK_START_RE = re.compile(r"^\s*(struct_union|union|struct)\s*\{\s*$")


def fail(message: str) -> "NoReturn":
    """Report a usage or I/O problem and exit with status 2."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


@dataclass
class AbiType:
    name: str
    size: int


def read_abi_stg(path: Path) -> dict[str, AbiType]:
    """Parse the frozen ABI description.

    The file is protobuf text format.  Each entry looks like::

        struct_union {
          id: 0x7c4a4a84
          kind: STRUCT
          name: "address_space"
          definition {
            bytesize: 240
            member_id: 0xb8efa234
            ...
          }
        }

    Only the name and bytesize are needed here; member ids are what the
    upstream tooling diffs, but a size change already implies a layout change
    and is the cheap, dependency-free check.
    """
    types: dict[str, AbiType] = {}
    current: str | None = None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if BLOCK_START_RE.match(line):
                current = None
                continue
            name_match = NAME_RE.match(line)
            if name_match:
                current = name_match.group(1)
                continue
            size_match = SIZE_RE.match(line)
            if size_match and current:
                types[current] = AbiType(current, int(size_match.group(1)))
                current = None
    return types


def read_vmlinux_sizes(vmlinux: Path, pahole: str) -> dict[str, int]:
    """Return {type name: size in bytes} for every type pahole knows about."""
    result = subprocess.run(
        [pahole, "--sizes", str(vmlinux)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fail(f"pahole failed on {vmlinux}: {result.stderr.strip()[:200]}")

    sizes: dict[str, int] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, size_text = parts[0].strip(), parts[1].strip()
        if not name or not size_text.isdigit():
            continue
        sizes[name] = int(size_text)
    return sizes


BASELINE_VERSION = 1


def read_baseline(path: Path) -> tuple[dict[str, int], str]:
    """Return ({type: size}, origin description) from a recorded baseline."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sizes = {k: int(v) for k, v in data.get("sizes", {}).items()}
    return sizes, data.get("origin", "unknown")


def write_baseline(path: Path, sizes: dict[str, int], origin: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"version": BASELINE_VERSION, "origin": origin, "sizes": sizes},
            indent=0,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


@dataclass
class Report:
    checked: int = 0
    matched: int = 0
    changed: list[tuple[str, int, int]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.changed


def compare(
    frozen: dict[str, AbiType], actual: dict[str, int]
) -> Report:
    report = Report()
    for name, entry in frozen.items():
        report.checked += 1
        size = actual.get(name)
        if size is None:
            # Types only present on other architectures, or optimised out
            # because nothing references them in this build.
            report.missing.append(name)
            continue
        if size == entry.size:
            report.matched += 1
        else:
            report.changed.append((name, entry.size, size))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--kernel",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="kernel tree root (default: parent of this script)",
    )
    parser.add_argument("--vmlinux", type=Path, help="override vmlinux path")
    parser.add_argument("--stg", type=Path, help="override ABI description path")
    parser.add_argument(
        "--baseline",
        type=Path,
        help="baseline JSON (default: <kernel>/docs/abi-baseline.json)",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="record the current build as the new baseline and exit",
    )
    parser.add_argument(
        "--use-stg",
        action="store_true",
        help="compare against the frozen .stg snapshot instead of the baseline",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--list-changed",
        action="store_true",
        help="only print changed types (suppress the summary header)",
    )
    args = parser.parse_args()

    stg = args.stg or args.kernel / "android/abi_gki_aarch64.stg"
    vmlinux = args.vmlinux or args.kernel / "vmlinux"
    baseline_path = args.baseline or args.kernel / "docs/abi-baseline.json"

    if not vmlinux.is_file():
        fail(f"vmlinux not found: {vmlinux} (build the kernel first)")

    pahole = shutil.which("pahole")
    if not pahole:
        fail("pahole not found; install dwarves to use this check")

    actual = read_vmlinux_sizes(vmlinux, pahole)
    if not actual:
        fail(f"pahole returned no types for {vmlinux}")

    if args.write_baseline:
        release = args.kernel / "include/config/kernel.release"
        origin = release.read_text().strip() if release.is_file() else "unknown"
        write_baseline(baseline_path, actual, origin)
        print(f"recorded {len(actual)} type sizes from {origin}")
        print(f"baseline written to {baseline_path}")
        return 0

    use_stg = args.use_stg or not baseline_path.is_file()
    if use_stg:
        if not stg.is_file():
            fail(f"ABI description not found: {stg}")
        frozen = read_abi_stg(stg)
        if not frozen:
            fail(f"no types parsed from {stg}")
        source = str(stg)
        origin = "frozen .stg snapshot"
        expected = {n: t.size for n, t in frozen.items()}
    else:
        expected, origin = read_baseline(baseline_path)
        if not expected:
            fail(f"baseline {baseline_path} is empty")
        source = str(baseline_path)

    report = compare(
        {n: AbiType(n, s) for n, s in expected.items()}, actual
    )

    if args.json:
        print(
            json.dumps(
                {
                    "reference": source,
                    "origin": origin,
                    "vmlinux": str(vmlinux),
                    "checked": report.checked,
                    "matched": report.matched,
                    "ok": report.ok,
                    "changed": [
                        {"type": n, "frozen": f, "built": b}
                        for n, f, b in report.changed
                    ],
                    "missing": report.missing,
                },
                indent=2,
            )
        )
        return 0 if report.ok else 1

    if not args.list_changed:
        print(f"reference       : {source}")
        print(f"reference origin: {origin}")
        print(f"kernel image    : {vmlinux}")
        print(f"types checked   : {report.checked}")
        print(f"types matched   : {report.matched}")
        print(f"types not built : {len(report.missing)}")
        print()

    for name, frozen_size, built_size in sorted(report.changed):
        delta = built_size - frozen_size
        print(f"[CHANGED] {name}: frozen {frozen_size} -> built {built_size} "
              f"({delta:+d} bytes)")

    if report.ok:
        if not args.list_changed:
            print("All frozen ABI types keep their original size.")
            print("Safe to load against prebuilt vendor modules.")
        return 0

    print()
    print(f"{len(report.changed)} ABI type(s) changed size.")
    print()
    print("Prebuilt vendor modules were compiled against the frozen layout, and")
    print("CONFIG_MODULE_FORCE_LOAD=y makes the kernel load them regardless of the")
    print("CRC mismatch. They will then access fields at wrong offsets and corrupt")
    print("memory, typically hanging the device at the boot logo.")
    print()
    print("Find the Kconfig option or patch that changed the layout before flashing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
