# Xiaomi Rodin Kernel Enhance

[![Kernel](https://img.shields.io/badge/kernel-6.6.143_LTS-blue)](https://kernel.org)
[![Base](https://img.shields.io/badge/base-MiCode%20bsp--rodin--v--oss-orange)](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss)
[![Root](https://img.shields.io/badge/Root-ReSukiSU-green)](https://github.com/ReSukiSU/ReSukiSU)
[![SuSFS](https://img.shields.io/badge/Hiding-SuSFS-green)](https://gitlab.com/simonpunk/susfs4ksu)
[![License](https://img.shields.io/badge/license-GPL--2.0-lightgrey)](LICENSES)

[简体中文](README.md) | English

An enhanced Android kernel for Xiaomi **rodin** devices, built on top of Xiaomi's released [`bsp-rodin-v-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss) kernel source (AOSP `android15-6.6` GKI / MediaTek) and kept in sync with the latest **6.6 LTS**.

> **Note:** This project is forked and modified from [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance). Many thanks to the original author for the initial work!

## Highlights

### Root & Hiding
- **ReSukiSU** built-in, integrated from [`ReSukiSU/ReSukiSU` (`main`)](https://github.com/ReSukiSU/ReSukiSU/tree/main)
- **SuSFS** built-in, integrated from [`omajili-manbu/susfs4ksu` (`gki-android15-6.6-mod`)](https://github.com/omajili-manbu/susfs4ksu/tree/gki-android15-6.6-mod)
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
- **CAKE Smart Queue Management**: built-in Common Applications Kept Enhanced (CAKE) qdisc for best-in-class bufferbloat mitigation, flow isolation, and minimal gaming latency
- **Foreground I/O Latency Protection & WBT**: enabled `BLK_CGROUP_IOLATENCY` and `BLK_WBT_MQ` to prioritize foreground interactive/gaming I/O and prevent writeback storms from starving read requests
- **DAMON Physical Memory Monitoring & LRU Sorting**: enabled `DAMON_PADDR`, `DAMON_RECLAIM`, and `DAMON_LRU_SORT` to proactively protect active working sets and reclaim cold pages, boosting multitasking retention

### Stability & Fixes
- Fixed probabilistic boot hang and restored vendor module compatibility
- Backported upstream fixes on top of Xiaomi's official kernel

The tuning philosophy is **balancing performance and battery life** — all gains come from compile-time optimizations, an up-to-date kernel, updated algorithms, and bug fixes on top of Xiaomi's official kernel, with no aggressive tweaks biased toward either side.

## Current Status & Recent Updates

- **Kernel Version**: Linux 6.6.143 (Android 15 GKI)
- **Target Platform**: Xiaomi Rodin / MT6897 (Dimensity 8400 Ultra)
- **Stable Baseline**: `5029f1d845df`
- **Network Stack Optimization**: Kernel-level hard-lock for **BBRv3** TCP congestion control and **FQ** packet scheduler, preventing Android userspace overrides and ensuring system-wide activation

### Verified Scheduler Backports
The following 6 scheduler backports have been audited, applied, compiled, and individually verified via hardware flashing tests on physical Rodin devices:
- `sched/fair: Fix cpu_util runnable_avg arithmetic`
- `sched/fair: Allow decaying util_est when util_avg > CPU capa`
- `sched/fair: Fix overflow in update_tg_cfs_runnable()`
- `sched/fair: Fix initial util_avg calculation`
- `sched/fair: Don't trigger active lb if src_rq->curr is not on_rq`
- `sched/fair: Check CPU capacity before comparing group types during load balance`

Subsequent scheduler backports will continue to be audited, built, and hardware-verified step by step.

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
- [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) / [SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) / [KernelSU](https://github.com/tiann/KernelSU) — root solution
- [SusFS](https://gitlab.com/simonpunk/susfs4ksu) — root hiding
- [Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) — brick protection
- [Linux-Patches](https://gitlab.com/xanmod/linux-patches) — BBRv3 patches
- AOSP `android15-6.6` / upstream Linux 6.6 LTS

## License

This repository is licensed under **GPL-2.0**, following the Linux kernel and the upstream sources it is based on. See [LICENSES](LICENSES) for details.
