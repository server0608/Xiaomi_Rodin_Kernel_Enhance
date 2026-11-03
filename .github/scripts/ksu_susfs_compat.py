#!/usr/bin/env python3
"""Restore the reviewed BakaSU/SUSFS helper interface after vendoring.

This adapts symbol visibility only. Unknown helper signatures abort the sync;
it does not update SUSFS, bypass upstream build guards, or prove runtime
compatibility with a newer BakaSU implementation.
"""

import argparse
from pathlib import Path
import re


SIGNATURES = {
    "security_context_to_sid_with_policy": (
        "struct selinux_policy *policy, const char *scontext, u32 scontext_len, "
        "u32 *sid, u32 def_sid, gfp_t gfp_flags, u32 *orig_sid_p, int *orig_rc_p",
        2,
    ),
    "security_sid_to_context_with_policy": (
        "struct selinux_policy *policy, u32 sid, char **scontext, u32 *scontext_len",
        1,
    ),
}


def compact(text):
    return re.sub(r"\s+", "", text)


def adapt(root):
    header = root / "include/linux/ksu_susfs_compat.h"
    source = root / "drivers/kernelsu/feature/selinux_hide.c"
    text = source.read_text()
    shared = header.read_text()

    for name, (expected, count) in SIGNATURES.items():
        pattern = re.compile(
            r"^(static|__maybe_static) int " + name + r"\s*\(([^)]*)\)",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        if len(matches) != count:
            raise ValueError(f"{name}: expected {count} declarations/definitions, got {len(matches)}")
        for match in matches:
            if compact(match.group(2)) != compact(expected):
                raise ValueError(f"{name}: upstream signature changed; manual review required")
        declaration = re.search(r"int " + name + r"\s*\(([^)]*)\);", shared)
        if not declaration or compact(declaration.group(1)) != compact(expected):
            raise ValueError(f"{name}: shared header signature mismatch")
        text = pattern.sub(lambda m: "__maybe_static" + m.group(0)[len(m.group(1)):], text)

    # The kernel call sites pass NULL for the new optional outputs. Require
    # the reviewed implementation's NULL guards before allowing a sync.
    for output in ("orig_sid_p", "orig_rc_p"):
        if not re.search(r"if\s*\(\s*" + output + r"\s*\)", text):
            raise ValueError(f"{output}: optional-output guard missing; manual review required")

    old = "#ifdef KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE\n#define __maybe_static"
    new = "#ifdef KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE\n#include <linux/ksu_susfs_compat.h>\n#define __maybe_static"
    if text.count(new) != 1:
        if text.count(old) != 1 or "#include <linux/ksu_susfs_compat.h>" in text:
            raise ValueError("SUSFS helper visibility guard changed; manual review required")
        text = text.replace(old, new, 1)

    if source.read_text() != text:
        source.write_text(text)
        print("Adapted BakaSU helper visibility to the shared SUSFS interface")
    else:
        print("BakaSU/SUSFS helper interface already adapted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        adapt(args.root)
    except (OSError, ValueError) as error:
        parser.exit(1, f"BakaSU/SUSFS compatibility check failed: {error}\n")


if __name__ == "__main__":
    main()
