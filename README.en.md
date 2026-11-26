# Xiaomi Rodin Kernel Enhance

[![Kernel](https://img.shields.io/badge/kernel-6.6.162_LTS-blue)](https://kernel.org)
[![Base](https://img.shields.io/badge/base-MiCode%20bsp--rodin--v--oss-orange)](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss)
[![Root](https://img.shields.io/badge/Root-BakaSU-green)](https://github.com/Baka-SU/BakaSU)
[![SuSFS](https://img.shields.io/badge/Hiding-SuSFS-green)](https://gitlab.com/simonpunk/susfs4ksu)
[![License](https://img.shields.io/badge/license-GPL--2.0-lightgrey)](LICENSES)

[简体中文](README.md) | English

An enhanced Android kernel for Xiaomi **rodin** devices, built on top of Xiaomi's released [`bsp-rodin-v-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss) kernel source (AOSP `android15-6.6` GKI / MediaTek) and kept in sync with the latest **6.6 LTS**.

> **Note:** This project is forked and modified from [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance). Many thanks to the original author for the initial work!

## Highlights

### Root & Hiding
- **BakaSU** (formerly ReSukiSU) built-in, integrated from [`Baka-SU/BakaSU` (`main`)](https://github.com/Baka-SU/BakaSU/tree/main)
- **SuSFS v2.4.0** built-in, based on official [`simonpunk/susfs4ksu` (`gki-android15-6.6`)](https://gitlab.com/simonpunk/susfs4ksu/-/tree/gki-android15-6.6) with selective SELinux hiding patches and `open_redirect` spoofing layered from [`omajili-manbu/susfs4ksu` (`gki-android15-6.6-mod`)](https://github.com/omajili-manbu/susfs4ksu/tree/gki-android15-6.6-mod)
- Able to hide suspicious SELinux contexts/rules from apps, tied to the SuSFS AVC log spoofing switch

### Brick Protection
- **Baseband-guard (BBG)** LSM: blocks unauthorized writes to critical partitions/device nodes at the kernel level ([vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard), allowlist adjusted for rodin)

### Performance
- Cortex-A725 compiler tuning (clang 19+)
- **ThinLTO** link-time optimization
- **AutoFDO** link-time optimization guided by real-world profiles (clang 17+)
- **BBRv3** as the default TCP congestion control, with **fq** as the companion queueing discipline
- **ZSTD** upgraded to v1.5.7
- ZRAM built-in with a full compression algorithm set, default LZ4
- **Enhanced I/O Schedulers**: built-in **Kyber** (low-latency queue depth auto-tuning for fast UFS storage) and **BFQ** (hierarchical cgroup scheduling) to eliminate UI stuttering during heavy background I/O
- **Socket & Network Diagnostics**: complete in-kernel TCP/UDP/RAW socket diagnostics for smoother loopback and local proxy traffic
- **RCU Lazy Power Savings Enabled by Default**: batch and delay non-urgent RCU callbacks to reduce spurious CPU wakeups from low-power idle states, boosting screen-off standby battery life
- **EROFS High-Priority Multithreaded Decompression**: per-CPU high-priority decompression workers enabled with LZMA/DEFLATE support for faster app cold-starts
- **Stripped Redundant Kernel Debug Overhead**: disabled heavy page-owner tracking to reduce memory allocation stalls and standby power draw
- **Foreground I/O Latency Protection & WBT**: enabled `BLK_CGROUP_IOLATENCY` and `BLK_WBT_MQ` to prioritize foreground interactive/gaming I/O and prevent writeback storms from starving read requests
- **DAMON Physical Memory Monitoring & LRU Sorting**: enabled `DAMON_PADDR`, `DAMON_RECLAIM`, and `DAMON_LRU_SORT` to proactively protect active working sets and reclaim cold pages, boosting multitasking retention

### Stability & Fixes
- Fixed probabilistic boot hang and restored vendor module compatibility
- Backported upstream fixes on top of Xiaomi's official kernel

The tuning philosophy is **balancing performance and battery life** — all gains come from compile-time optimizations, an up-to-date kernel, updated algorithms, and bug fixes on top of Xiaomi's official kernel, with no aggressive tweaks biased toward either side.

## Current Status & Recent Updates

- **Kernel Version**: Linux 6.6.162 (Android 15 GKI)
- **Target Platform**: Xiaomi Rodin / MT6897 (Dimensity 8400 Ultra)
- **AOSP Baseline**: `android15-6.6-lts` @ `8e5968bb7aca` (merge commit `bf641bbe26e9`, resolving the single conflict in `drivers/ufs/core/ufs-mcq.c` and updating `net/ipv4/tcp_bbr3_compat.h` for the 3-argument `__tcp_send_ack()`)
- **Root Component**: BakaSU `57b2db60` (tag `v4.2.0-rc3`), Version Code **35285**, UAPI **6**; use the [official manager from the same commit](https://github.com/Baka-SU/BakaSU/actions/runs/45221593387).
- **SuSFS Upgrade & Compatibility**: Kernel-side SuSFS upgraded to official **v2.4.0** (`f98f082`), natively matching BakaSU `57b2db60`'s split `selinux_hide` module with `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y` enabled; selective SELinux hiding patches and `open_redirect` spoofing are preserved, and `preinit/runner.elf` remains disabled (`-DKSU_NO_PREINIT`, including `fs/exec.c`).
- **Validation Status**: Clean local build (`6.6.162`), ARM64 / LZ4 Legacy magic verification, frozen GKI `.stg` check (3,264/3,267 matched, only the 3 pre-existing `ZSTD_*` divergences; 641/641 `abi_gki_aarch64_xiaomi` symbols exported), and the refreshed 10,815-type baseline check all pass. **Physical device testing for this `6.6.162` + SuSFS v2.4.0 + BakaSU `57b2db60` combination is still pending** (the previous `6.6.144` release was verified on Rodin for boot, manager recognition, and installed modules).
- **Network Stack & MGLRU Hard-Locks**: Kernel-level hard-locks keep **BBRv3** TCP congestion control, **FQ** packet scheduler, and **MGLRU** core reclaim enabled against Android/MIUI userspace `init.rc` overrides.
- **ABI Protection**: `scripts/abi-guard.py` compares the size of all 10,815 recorded kernel types in `docs/abi-baseline.json` (and supports `--use-stg` against the frozen GKI `.stg` snapshot) after every build to catch struct layout drift before flashing. Prebuilt vendor modules are compiled against the frozen GKI layout, and the kernel does not refuse mismatched symbol CRCs under `CONFIG_MODULE_FORCE_LOAD=y`.

### Included Upstream Backports

Of the 17 backports originally carried on top of 6.6.144, **6** are now natively included via the AOSP `android15-6.6-lts` (6.6.162) merge and **11** remain as local backports. Validation is documented in the respective build and device-test records; a successful build does not imply an independent A/B test.

**Active Local Backports (11)**

*Scheduling (`sched/fair`)*
- `sched/fair: Allow decaying util_est when util_avg > CPU capa`
- `sched/fair: Fix initial util_avg calculation`
- `sched/fair: Don't trigger active lb if src_rq->curr is not on_rq`
- `sched/fair: Don't double balance_interval for migrate_misfit`
- `sched/fair: Do strict inequality check for busiest misfit task group`
- `sched/fair: Filter false overloaded_group case for EAS`
- `sched/fair: optimize the PLACE_LAG when se->vlag is zero`
- `sched/fair: Update overutilized detection`
- `sched/balance: Skip unnecessary updates to idle load balancer's flags`

*Scheduling / idle*
- `sched: idle: Optimize the generic idle loop by removing needless memory barrier`

*Frequency scaling* (inert on this device: MTK's `cpufreq_sugov_ext` module is the active governor)
- `cpufreq/sched: Explicitly synchronize limits_changed flag handling`

**Now Included Upstream in AOSP 6.6.162 (6)**
- `sched/fair: Fix cpu_util runnable_avg arithmetic` (6.6.145)
- `sched/fair: Only update stats for allowed CPUs when looking for dst group` (6.6.145)
- `sched/fair: Fix overflow in update_tg_cfs_runnable()` (6.6.157)
- `sched/fair: Check CPU capacity before comparing group types during load balance` (6.6.157)
- `mm/migrate: report RCU-tasks quiescent states in migrate_pages_batch()` (6.6.157)
- `net/sched: fq: add overflow bounds to quantum and initial quantum` (6.6.160)

Every candidate is audited individually, kept to a minimal diff, built locally,
checked against the frozen GKI ABI, and only then verified on hardware. A patch
that changes the layout of a struct in the frozen ABI is rejected regardless of
its benefit, because prebuilt vendor modules are compiled against that layout.

## Supported Devices

| Device | Codename | OS |
|---|---|---|
| Redmi Turbo 4 | rodin | HyperOS 3 (Android 16) |
| POCO X7 Pro | rodin | HyperOS 3 (Android 16) |

> **Note:** Untested on POCO hardware, but it should work — Xiaomi ships the same kernel source for the POCO and Redmi variants. If you run into any issues, feel free to open an issue with logs attached, and I'll try to fix it.

## Branches

- [`bsp-rodin-v-oss-bp`](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/tree/bsp-rodin-v-oss-bp) — main build branch, based on Xiaomi's official rodin source with additional backports and enhancements

## Roadmap

- HyperOS 4 support is planned

## Downloads & Support

- [Some build guides](BUILD-GUIDE.md)
- Prebuilt images: [Releases](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/releases)
- Bug reports: open an [issue](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/issues) with kernel logs attached
- If you like this project, please consider giving it a Star to support me!

## Acknowledgements

- [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance) — original repository and enhancement work
- [MiCode/Xiaomi_Kernel_OpenSource](https://github.com/MiCode/Xiaomi_Kernel_OpenSource) — official rodin kernel source (`bsp-rodin-v-oss`)
- [BakaSU](https://github.com/Baka-SU/BakaSU) / [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) / [SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) / [KernelSU](https://github.com/tiann/KernelSU) — root solution
- [SusFS](https://gitlab.com/simonpunk/susfs4ksu) — root hiding
- [Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) — brick protection
- [Linux-Patches](https://gitlab.com/xanmod/linux-patches) — BBRv3 patches
- AOSP `android15-6.6` / upstream Linux 6.6 LTS

## License

This repository is licensed under **GPL-2.0**, following the Linux kernel and the upstream sources it is based on. See [LICENSES](LICENSES) for details.
