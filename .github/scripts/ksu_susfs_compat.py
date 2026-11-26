#!/usr/bin/env python3
"""Verify the BakaSU/ReSukiSU <-> in-tree SUSFS v2.4.0 interface contract.

With official SUSFS v2.4.0, security/selinux/{hooks,selinuxfs,ss/services}.c
no longer call BakaSU's backup-policy helpers directly. Instead, BakaSU and the
in-tree SUSFS hooks share a smaller, well-defined symbol surface and preinit
disablement contract. Any structural surprise aborts sync/CI before push/build.
"""

import argparse
from pathlib import Path
import re


REQUIRED_SELINUX_HIDE_EXPORTS = (
    r"__maybe_static\s+bool\s+ksu_selinux_hide_running\b",
    r"__maybe_static\s+DEFINE_STATIC_KEY_FALSE\s*\(\s*fake_status_initialize_key\s*\)",
    r"__maybe_static\s+struct\s+page\s*\*\s*fake_status\b",
    r"__maybe_static\s+void\s+initialize_fake_status\s*\(",
)

REQUIRED_SUSFS_V240_SYMBOLS = (
    "susfs_add_sus_type",
    "susfs_add_sus_avd_allowed_by_type",
    "susfs_parse_sus_path_app_strings",
    "susfs_parse_priority_app_strings",
    "susfs_set_sus_path_uid_filter",
    "susfs_set_priority_uid_filter",
    "susfs_is_avc_log_spoofing_enabled",
    "susfs_open_redirect_spoof_do_sys_openat",
    "susfs_open_redirect_spoof_show_map_vma_srcu",
)

REQUIRED_KERNEL_HOOK_MARKERS = {
    "security/selinux/hooks.c": (
        "ksu_selinux_hide_running",
        "susfs_security_context_to_sid",
    ),
    "security/selinux/selinuxfs.c": (
        "ksu_selinux_hide_running",
        "susfs_security_context_to_sid",
        "susfs_security_context_str_to_sid",
        "susfs_security_compute_av_user",
        "fake_status",
    ),
    "security/selinux/ss/services.c": (
        "susfs_security_context_to_sid",
        "susfs_security_context_str_to_sid",
        "susfs_security_compute_av_user",
        "susfs_is_sus_type_rcu",
        "susfs_spoof_avd_allowed_rcu",
    ),
    "security/selinux/status.c": (
        "susfs_is_current_ksu_domain",
    ),
}


def require_file(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def verify(root: Path) -> None:
    # 1) BakaSU SUSFS compat detector & selinux_hide split layout.
    compat_mk = require_file(root / "drivers/kernelsu/tools/susfs_compat.mk")
    if "ksu_selinux_hide_running" not in compat_mk or "KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE" not in compat_mk:
        raise ValueError("drivers/kernelsu/tools/susfs_compat.mk changed selinux_hide detection")

    selinux_hide_c = require_file(root / "drivers/kernelsu/feature/selinux_hide/selinux_hide.c")
    require_file(root / "drivers/kernelsu/feature/selinux_hide/selinux_hide_susfs.c")
    if '#include "selinux_hide_susfs.c"' not in selinux_hide_c:
        raise ValueError("selinux_hide.c no longer includes selinux_hide_susfs.c")
    for pattern in REQUIRED_SELINUX_HIDE_EXPORTS:
        if not re.search(pattern, selinux_hide_c):
            raise ValueError(f"selinux_hide.c missing expected __maybe_static export matching: {pattern}")

    # 2) Kernel-side SUSFS v2.4.0 core symbols & SELinux hook markers.
    susfs_c = require_file(root / "fs/susfs.c")
    for sym in REQUIRED_SUSFS_V240_SYMBOLS:
        if sym not in susfs_c:
            raise ValueError(f"fs/susfs.c missing required SUSFS v2.4.0 symbol: {sym}")

    for rel_path, markers in REQUIRED_KERNEL_HOOK_MARKERS.items():
        text = require_file(root / rel_path)
        for marker in markers:
            if marker not in text:
                raise ValueError(f"{rel_path} missing expected SUSFS v2.4.0 marker: {marker}")

    # 3) Preinit runner must stay disabled in both KSU and fs/exec.c.
    codegen_mk = require_file(root / "drivers/kernelsu/tools/code_generation/code_generation.mk")
    if "preinit_runner.mk" in codegen_mk or "-DKSU_NO_PREINIT" not in codegen_mk:
        raise ValueError("code_generation.mk must disable preinit_runner.mk and define -DKSU_NO_PREINIT")

    fs_makefile = require_file(root / "fs/Makefile")
    if not re.search(r"CFLAGS_exec\.o\s*\+=\s*-DKSU_NO_PREINIT", fs_makefile):
        raise ValueError("fs/Makefile must pass -DKSU_NO_PREINIT to exec.o to match KSU")

    print("BakaSU/SUSFS v2.4.0 interface contract verified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        verify(args.root)
    except (OSError, ValueError) as error:
        parser.exit(1, f"BakaSU/SUSFS compatibility check failed: {error}\n")


if __name__ == "__main__":
    main()
