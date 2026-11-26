#!/usr/bin/env python3
"""Pin ReSukiSU version info into the vendored drivers/kernelsu/Kbuild.

The kernel tree carries an in-tree copy of the ReSukiSU kernel module, so the
Kbuild must never query git there (it would report the kernel repo's commit
count / sha / dirty state). This script pins the four version fields computed
from the ReSukiSU checkout, per BUILD-GUIDE.md:

    KSU_VERSION = 30000 + KSU_LOCAL_VERSION + 700

It handles two input states:
  1. Upstream git-query form  -> the whole version block is replaced with the
     pinned form (what fix_kbuild.py does after a fresh rsync landing);
  2. Already-pinned form      -> the pinned values are updated in place.

Anything else (upstream Kbuild restructured) is a hard error: exit 2 so the
calling workflow stops instead of shipping a broken pin.
"""

import argparse
import re
import sys

START_ANCHOR = (
    "LOCAL_GIT_EXISTS := $(shell test -e $(KSU_SRC)/../.git && echo 1 || echo 0)"
)
END_ANCHORS = (
    'KSU_BRANCH_NAME := $(shell cd $(KSU_SRC); $(GIT_BIN) branch --show-current 2>/dev/null || echo "unknown")',
    "KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)",
)
VENDORED_MARKER = "Vendored as an in-tree copy of ReSukiSU"

TEMPLATE = """\
LOCAL_GIT_EXISTS := $(shell test -e $(KSU_SRC)/../.git && echo 1 || echo 0)

ifeq ($(LOCAL_GIT_EXISTS),0)
$(info -- $(REPO_NAME) sources are vendored in-tree; pinning version info to the vendored snapshot)
endif

ifdef KBUILD_EXTMOD
include $(KSU_SRC)/tools/ddk_compatible.mk
endif

ifeq ($(LOCAL_GIT_EXISTS),1)
$(shell cd $(KSU_SRC); [ -f ../.git/shallow ] && $(GIT_BIN) fetch --unshallow)
KSU_LOCAL_VERSION := $(shell cd $(KSU_SRC); $(GIT_BIN) rev-list --count HEAD)
KSU_TAG_NAME    := $(shell cd $(KSU_SRC); $(GIT_BIN) describe --abbrev=0 --tags 2>/dev/null || echo "v4.1.0")
KSU_COMMIT_SHA  := $(shell cd $(KSU_SRC); $(GIT_BIN) rev-parse --short=8 HEAD 2>/dev/null || echo "unknown")
ifneq ($(shell cd $(KSU_SRC); $(GIT_BIN) diff-index --quiet HEAD; echo $$?),0)
KSU_COMMIT_SHA  := $(KSU_COMMIT_SHA)-dirty
endif
KSU_BRANCH_NAME := $(shell cd $(KSU_SRC); $(GIT_BIN) branch --show-current 2>/dev/null || echo "unknown")
else
# Vendored as an in-tree copy of ReSukiSU {branch} @ {sha8} (tag {tag}). Do NOT
# query git here: this directory lives inside the kernel git repository, so
# rev-list, rev-parse and diff-index would silently report the kernel tree
# history and leak its commit count, sha and dirty state into the ReSukiSU
# version info.
KSU_LOCAL_VERSION := {count}
KSU_TAG_NAME    := {tag}
KSU_COMMIT_SHA  := {sha8}
KSU_BRANCH_NAME := {branch}
endif
KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)"""


def fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kbuild", required=True)
    ap.add_argument("--count", required=True, type=int)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sha8", required=True)
    ap.add_argument("--branch", required=True)
    args = ap.parse_args()

    with open(args.kbuild, "r", encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")

    def render() -> str:
        return TEMPLATE.format(
            branch=args.branch, sha8=args.sha8, tag=args.tag, count=args.count
        )

    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == START_ANCHOR)
        end_candidates = [
            i
            for i, l in enumerate(lines[start:], start)
            if l.strip() in END_ANCHORS
        ]
        if not end_candidates:
            raise StopIteration
        end = max(end_candidates)
    except StopIteration:
        start = None

    # Distinguish an already-pinned Kbuild from a fresh upstream Kbuild.
    if start is not None and any(VENDORED_MARKER in l for l in lines[start : end + 1]):
        start = None

    if start is not None:
        lines[start : end + 1] = render().split("\n")
        mode = "replaced upstream git-query block with pinned values"
    else:
        # Already-pinned form: update values only inside the vendored block.
        try:
            marker = next(i for i, l in enumerate(lines) if VENDORED_MARKER in l)
            end = next(
                i for i, l in enumerate(lines[marker:], marker) if l.strip() == "endif"
            )
        except StopIteration:
            return fail(
                "neither the upstream git-query block nor the pinned block was "
                "found in the Kbuild; upstream likely changed its structure - "
                "manual review required"
            )
        seg = "\n".join(lines[marker:end])
        subs = [
            (r"KSU_LOCAL_VERSION := \d+", f"KSU_LOCAL_VERSION := {args.count}"),
            (r"KSU_TAG_NAME    := \S+", f"KSU_TAG_NAME    := {args.tag}"),
            (
                r"KSU_COMMIT_SHA  := [0-9a-f]{8}(?:-dirty)?",
                f"KSU_COMMIT_SHA  := {args.sha8}",
            ),
            (r"KSU_BRANCH_NAME := \S+", f"KSU_BRANCH_NAME := {args.branch}"),
            (r"ReSukiSU \S+ @ [0-9a-f]{8}", f"ReSukiSU {args.branch} @ {args.sha8}"),
        ]
        for pattern, repl in subs:
            seg, n = re.subn(pattern, repl, seg)
            if n != 1:
                return fail(f"pinned-block pattern {pattern!r} matched {n} times")
        lines[marker:end] = seg.split("\n")
        mode = "updated pinned values in vendored block"

    # Guard against leaked upstream git queries after the pinned block.
    result = "\n".join(lines)
    after_version = result.split("KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)", 1)
    if len(after_version) != 2 or "$(GIT_BIN)" in after_version[1]:
        return fail(
            "unexpected $(GIT_BIN) query remains after pinned KSU_VERSION block - "
            "upstream Kbuild structure likely changed"
        )

    with open(args.kbuild, "w", encoding="utf-8", newline="\n") as f:
        f.write(result)
    print(
        f"OK ({mode}): count={args.count} tag={args.tag} "
        f"sha={args.sha8} branch={args.branch}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
