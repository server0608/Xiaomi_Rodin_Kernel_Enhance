/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_KSU_SUSFS_COMPAT_H
#define _LINUX_KSU_SUSFS_COMPAT_H

#include <linux/gfp_types.h>
#include <linux/types.h>

struct selinux_policy;

/*
 * Private in-tree interface between BakaSU's backup-policy helpers and the
 * SUSFS SELinux call sites. The last two outputs are optional; callers that
 * only validate a context against the backup policy pass NULL for both.
 * Keep these declarations shared so interface changes fail at compile time.
 */
int security_context_to_sid_with_policy(struct selinux_policy *policy,
		const char *scontext, u32 scontext_len, u32 *sid, u32 def_sid,
		gfp_t gfp_flags, u32 *orig_sid_p, int *orig_rc_p);
int security_sid_to_context_with_policy(struct selinux_policy *policy,
		u32 sid, char **scontext, u32 *scontext_len);

#endif /* _LINUX_KSU_SUSFS_COMPAT_H */
