#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Verify prebuilt vendor kernel modules against this kernel's symbol CRCs.

GKI splits a device kernel in two:

  * the ``Image`` we build and flash into the ``boot`` partition, and
  * closed-source vendor ``.ko`` files that Xiaomi/MediaTek ship inside
    ``vendor_dlkm`` / ``vendor_boot`` and that we can never rebuild.

Those modules were compiled against a specific ABI.  When a module is loaded,
``check_version()`` in ``kernel/module/version.c`` compares the CRC of every
imported symbol against the CRC recorded in the module's ``__versions``
section.  A CRC is derived from the symbol signature *and* the layout of the
types it touches, so adding a field to an exported struct changes the CRC.

The catch: this kernel is built with ``CONFIG_MODULE_FORCE_LOAD=y``, and
``try_to_force_load()`` then returns 0 unconditionally.  A CRC mismatch does
not reject the module -- it only taints the kernel and lets the module run
against an ABI it was not compiled for.  That fails later as silent memory
corruption and random panics, so the mismatch has to be caught *before*
flashing.  This script does that.

Usage:
    # check every vendor module pulled from a device
    adb pull /vendor/lib/modules ./vendor-modules
    scripts/kmi-crc-check.py ./vendor-modules

    # check one module against an explicit symbol table
    scripts/kmi-crc-check.py --symvers vmlinux.symvers mtk_disp.ko

    # machine-readable, for CI
    scripts/kmi-crc-check.py --json ./vendor-modules

Exit status: 0 when every imported symbol matches, 1 when a mismatch or a
missing export is found, 2 on a usage or I/O error.

Only symbols exported by the kernel binary are compared.  A module that
depends on another module may therefore report symbols as "not exported by
this kernel"; treat those as informational unless the exporting module is
also absent from the device.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

ELF_MAGIC = b"\x7fELF"
SHT_STRTAB = 3
VERSIONS_SECTION = "__versions"
MODULE_LAYOUT = "module_layout"

# struct modversion_info is { unsigned long crc; char name[MODULE_NAME_LEN]; }
# with MODULE_NAME_LEN == (64 - sizeof(unsigned long)), so one entry is always
# 64 bytes; only the split between crc and name depends on the ELF class.
ENTRY_SIZE = 64


class ElfError(Exception):
    """Raised when a file is not a usable ELF object."""


def fail(message: str) -> "NoReturn":
    """Report a usage or I/O problem and exit with status 2."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


@dataclass
class ElfSection:
    name: str
    offset: int
    size: int
    entsize: int


def read_sections(data: bytes) -> list[ElfSection]:
    """Return the section table of an ELF image.

    Parsed by hand rather than with readelf/objdump so the check works on a
    build host without binutils for the target architecture.
    """
    if len(data) < 64 or data[:4] != ELF_MAGIC:
        raise ElfError("not an ELF file")

    elf_class = data[4]
    if elf_class not in (1, 2):
        raise ElfError(f"unsupported ELF class {elf_class}")
    is64 = elf_class == 2

    endian = data[5]
    if endian not in (1, 2):
        raise ElfError(f"unsupported ELF data encoding {endian}")
    order = "<" if endian == 1 else ">"

    # e_shoff / e_shentsize / e_shnum / e_shstrndx sit at different offsets
    # in the two ELF classes.
    if is64:
        shoff = struct.unpack_from(order + "Q", data, 0x28)[0]
        shentsize = struct.unpack_from(order + "H", data, 0x3A)[0]
        shnum = struct.unpack_from(order + "H", data, 0x3C)[0]
        shstrndx = struct.unpack_from(order + "H", data, 0x3E)[0]
    else:
        shoff = struct.unpack_from(order + "I", data, 0x20)[0]
        shentsize = struct.unpack_from(order + "H", data, 0x2E)[0]
        shnum = struct.unpack_from(order + "H", data, 0x30)[0]
        shstrndx = struct.unpack_from(order + "H", data, 0x32)[0]

    if not shoff or not shnum:
        raise ElfError("no section table")

    raw = []
    for index in range(shnum):
        base = shoff + index * shentsize
        if base + shentsize > len(data):
            raise ElfError("truncated section table")
        if is64:
            name_off, sh_type, _, _, sh_offset, sh_size = struct.unpack_from(
                order + "IIQQQQ", data, base
            )
            sh_entsize = struct.unpack_from(order + "Q", data, base + 0x38)[0]
        else:
            name_off, sh_type, _, _, sh_offset, sh_size = struct.unpack_from(
                order + "IIIIII", data, base
            )
            sh_entsize = struct.unpack_from(order + "I", data, base + 0x24)[0]
        raw.append((name_off, sh_type, sh_offset, sh_size, sh_entsize))

    if shstrndx >= len(raw):
        raise ElfError("invalid section name table index")
    strtab_off, strtab_size = raw[shstrndx][2], raw[shstrndx][3]
    strtab = data[strtab_off : strtab_off + strtab_size]

    def name_at(offset: int) -> str:
        end = strtab.find(b"\0", offset)
        if end < 0:
            end = len(strtab)
        return strtab[offset:end].decode("utf-8", "replace")

    sections = []
    for name_off, sh_type, sh_offset, sh_size, sh_entsize in raw:
        if sh_type == 0:  # SHT_NULL
            continue
        sections.append(
            ElfSection(name_at(name_off), sh_offset, sh_size, sh_entsize)
        )
    return sections


@dataclass
class ModuleVersions:
    """Symbol CRCs recorded inside a module's __versions section."""

    path: Path
    is64: bool
    crcs: dict[str, int] = field(default_factory=dict)


def read_module_versions(path: Path) -> ModuleVersions:
    data = path.read_bytes()
    if len(data) < 64 or data[:4] != ELF_MAGIC:
        raise ElfError("not an ELF file")

    is64 = data[4] == 2
    order = "<" if data[5] == 1 else ">"
    crc_size = 8 if is64 else 4
    name_len = ENTRY_SIZE - crc_size
    crc_format = order + ("Q" if is64 else "I")

    versions = ModuleVersions(path=path, is64=is64)
    section = next(
        (s for s in read_sections(data) if s.name == VERSIONS_SECTION), None
    )
    if section is None:
        # No __versions at all: the module was built without MODVERSIONS, so
        # the kernel cannot verify anything and loads it on trust.
        return versions

    entries = section.entsize or ENTRY_SIZE
    if entries < ENTRY_SIZE:
        raise ElfError(f"unexpected __versions entry size {entries}")

    body = data[section.offset : section.offset + section.size]
    for base in range(0, len(body) - ENTRY_SIZE + 1, entries):
        crc = struct.unpack_from(crc_format, body, base)[0]
        raw_name = body[base + crc_size : base + crc_size + name_len]
        name = raw_name.split(b"\0", 1)[0].decode("utf-8", "replace")
        if name:
            # The kernel compares against a 32-bit value.
            versions.crcs[name] = crc & 0xFFFFFFFF
    return versions


def read_symvers(paths: list[Path]) -> dict[str, int]:
    """Parse one or more vmlinux.symvers / Module.symvers files.

    Format: <crc>\\t<symbol>\\t<module>\\t<export>\\t[namespace]
    """
    crcs: dict[str, int] = {}
    for path in paths:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                crc_text, symbol = parts[0].strip(), parts[1].strip()
                if not symbol or not crc_text.startswith("0x"):
                    continue
                try:
                    crcs[symbol] = int(crc_text, 16) & 0xFFFFFFFF
                except ValueError:
                    continue
    return crcs


@dataclass
class Report:
    module: str
    versioned: int
    matched: int
    mismatched: list[tuple[str, int, int]]
    missing: list[str]
    unversioned: bool

    @property
    def ok(self) -> bool:
        return not self.mismatched and not self.missing


def check_module(path: Path, kernel_crcs: dict[str, int]) -> Report:
    versions = read_module_versions(path)
    mismatched: list[tuple[str, int, int]] = []
    missing: list[str] = []
    matched = 0

    for symbol, expected in sorted(versions.crcs.items()):
        actual = kernel_crcs.get(symbol)
        if actual is None:
            missing.append(symbol)
        elif actual != expected:
            mismatched.append((symbol, expected, actual))
        else:
            matched += 1

    return Report(
        module=path.name,
        versioned=len(versions.crcs),
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        unversioned=not versions.crcs,
    )


def collect_modules(targets: list[Path]) -> list[Path]:
    modules: list[Path] = []
    for target in targets:
        if target.is_dir():
            modules.extend(sorted(target.rglob("*.ko")))
        elif target.suffix == ".ko":
            modules.append(target)
        else:
            fail(f"{target} is neither a directory nor a .ko file")
    return modules


def default_symvers(kernel_root: Path) -> list[Path]:
    for name in ("vmlinux.symvers", "Module.symvers"):
        candidate = kernel_root / name
        if candidate.is_file():
            return [candidate]
    fail(
        f"no vmlinux.symvers in {kernel_root}; build the kernel first "
        "or pass --symvers"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("targets", nargs="+", type=Path, metavar="PATH")
    parser.add_argument(
        "--symvers",
        nargs="+",
        type=Path,
        help="symbol tables to compare against (default: <kernel>/vmlinux.symvers)",
    )
    parser.add_argument(
        "--kernel",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="kernel tree root used to find vmlinux.symvers",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--show-ok", action="store_true", help="also list modules that match"
    )
    args = parser.parse_args()

    symvers_paths = args.symvers or default_symvers(args.kernel)
    for path in symvers_paths:
        if not path.is_file():
            fail(f"symbol table not found: {path}")
    kernel_crcs = read_symvers(symvers_paths)

    modules = collect_modules(args.targets)
    if not modules:
        fail("no .ko files found")

    reports = []
    for module in modules:
        try:
            reports.append(check_module(module, kernel_crcs))
        except ElfError as exc:
            fail(f"{module}: {exc}")

    if args.json:
        print(
            json.dumps(
                {
                    "kernel_symbols": len(kernel_crcs),
                    "symvers": [str(p) for p in symvers_paths],
                    "modules": [
                        {
                            "module": r.module,
                            "versioned": r.versioned,
                            "matched": r.matched,
                            "ok": r.ok,
                            "unversioned": r.unversioned,
                            "mismatched": [
                                {"symbol": s, "module_crc": f"0x{m:08x}",
                                 "kernel_crc": f"0x{k:08x}"}
                                for s, m, k in r.mismatched
                            ],
                            "missing": r.missing,
                        }
                        for r in reports
                    ],
                },
                indent=2,
            )
        )
        return 0 if all(r.ok for r in reports) else 1

    print(f"kernel symbol table : {', '.join(str(p) for p in symvers_paths)}")
    print(f"exported symbols    : {len(kernel_crcs)}")
    print(f"modules checked     : {len(reports)}")
    print()

    for report in reports:
        if report.unversioned:
            print(f"[SKIP] {report.module}: no {VERSIONS_SECTION} section "
                  "(built without MODVERSIONS; kernel cannot verify it)")
            continue
        if report.ok and not args.show_ok:
            continue

        status = "OK  " if report.ok else "FAIL"
        print(f"[{status}] {report.module}: {report.matched}/{report.versioned} "
              f"symbols match")

        for symbol, module_crc, kernel_crc in report.mismatched:
            note = "  <-- struct layout changed" if symbol == MODULE_LAYOUT else ""
            print(f"    CRC mismatch  {symbol}")
            print(f"      module expects 0x{module_crc:08x}")
            print(f"      kernel exports 0x{kernel_crc:08x}{note}")

        if report.missing:
            print(f"    not exported by this kernel ({len(report.missing)}):")
            for symbol in report.missing[:20]:
                print(f"      {symbol}")
            if len(report.missing) > 20:
                print(f"      ... and {len(report.missing) - 20} more")

    failed = [r for r in reports if not r.ok]
    skipped = [r for r in reports if r.unversioned]
    passed = len(reports) - len(failed) - len(skipped)

    print()
    print(f"summary: {passed} ok, {len(failed)} failed, {len(skipped)} skipped")

    if failed:
        print()
        print("A CRC mismatch means the module was built against a different ABI.")
        print("CONFIG_MODULE_FORCE_LOAD=y makes the kernel load it anyway, so the")
        print("breakage appears later as memory corruption. Do not flash this image")
        print("with these modules.")
        return 1

    print("All compared symbols match; these modules are safe to load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
