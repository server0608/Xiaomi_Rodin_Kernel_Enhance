# Xiaomi Rodin Kernel Enhance

[![Kernel](https://img.shields.io/badge/kernel-6.6.162_LTS-blue)](https://kernel.org)
[![Base](https://img.shields.io/badge/base-MiCode%20bsp--rodin--v--oss-orange)](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss)
[![Root](https://img.shields.io/badge/Root-BakaSU-green)](https://github.com/Baka-SU/BakaSU)
[![SuSFS](https://img.shields.io/badge/Hiding-SuSFS-green)](https://gitlab.com/simonpunk/susfs4ksu)
[![License](https://img.shields.io/badge/license-GPL--2.0-lightgrey)](LICENSES)

简体中文 | [English](README.en.md)

基于小米已开源的 [`bsp-rodin-v-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss) 内核源码（AOSP `android15-6.6` GKI / 联发科）构建的 rodin 设备增强内核，并持续跟进最新 **6.6 LTS**。

> **说明：** 本项目 Fork 并修改自原作者仓库 [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance)，感谢原作者的前期工作！

## 特性

### Root 与隐藏
- 内置 **BakaSU**（原 ReSukiSU），集成自 [`Baka-SU/BakaSU`（`main`）](https://github.com/Baka-SU/BakaSU/tree/main)
- 内置 **SuSFS v2.4.0**，基于官方 [`simonpunk/susfs4ksu`（`gki-android15-6.6`）](https://gitlab.com/simonpunk/susfs4ksu/-/tree/gki-android15-6.6)，并叠加 [`omajili-manbu/susfs4ksu`（`gki-android15-6.6-mod`）](https://github.com/omajili-manbu/susfs4ksu/tree/gki-android15-6.6-mod) 的选择性 SELinux 隐藏补丁与 `open_redirect` 伪装支持
- 具备对应用隐藏可疑 SELinux 上下文/规则的能力，绑定在 SuSFS AVC 日志欺骗开关

### 防格机
- **Baseband-guard (BBG)** LSM：在内核层拦截对关键分区/设备节点的未授权写入（来自 [vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard)，白名单已针对 rodin 调整）

### 性能
- 针对 Cortex-A725 的编译优化（clang 19+）
- **ThinLTO** 链接优化
- **AutoFDO** 基于实际运行场景的链接优化（clang 17+）
- **BBRv3** 作为默认 TCP 拥塞控制，**fq** 作为配套网络队列调度
- **ZSTD** 升级至 v1.5.7
- ZRAM 内建，压缩算法补全，默认 LZ4
- **I/O 调度器补齐**：内建 **Kyber**（UFS 闪存低延迟自适应）与 **BFQ**（带 cgroups 分层调度），大幅抑制后台大读写时前台游戏的掉帧卡顿
- **网络套接字路径优化**：完整内建 TCP/UDP/RAW 套接字诊断模块，提升网络回环与本地代理流转效率
- **RCU Lazy 默认激活**：合并并延迟非紧急的 RCU 回调，减少 CPU 从低功耗睡眠态唤醒的次数，显著延长日常待机与息屏续航
- **EROFS 高优先级多线程解压**：默认启用 per-CPU 高调度优先级解压工作线程，支持 LZMA/DEFLATE，显著加快系统与应用冷启动速度
- **剥离冗余内核调试死重**：剔除冗余的页面分配调用栈追踪开销，降低系统调度延迟与背景功耗
- **前台 I/O 延迟保护与写回节流**：启用 `BLK_CGROUP_IOLATENCY` 与 `BLK_WBT_MQ`，优先保障前台游戏与交互的闪存读写响应，防止后台下载刷盘导致掉帧
- **DAMON 物理内存监控与热度排序**：启用 `DAMON_PADDR`、`DAMON_RECLAIM` 与 `DAMON_LRU_SORT`，动态监控访问热度，保护活跃热页并分流冷页，提升后台保活与内存吞吐

### 稳定性修复
- 修复概率性开机卡死，恢复 vendor 模块兼容
- 在小米官方内核基础上反向移植上游修复

调优理念是**性能与续航兼顾**——所有提升均来自编译时优化、更新的内核、更新的算法，以及对小米官方内核的 bug 修复，没有偏向任何一方的激进调整。

## 当前稳定状态与最近更新

- **内核版本**：Linux 6.6.162 (Android 15 GKI)
- **目标平台**：Xiaomi Rodin / MT6897 (Dimensity 8400 Ultra)
- **AOSP 基线**：`android15-6.6-lts` @ `8e5968bb7aca`（合并提交 `bf641bbe26e9`，已解决 `drivers/ufs/core/ufs-mcq.c` 唯一冲突并同步 `net/ipv4/tcp_bbr3_compat.h` 三参数 `__tcp_send_ack()`）
- **Root 组件**：BakaSU `57b2db60`（tag `v4.2.0-rc3`），Version Code **35285**，UAPI **6**；请使用[同提交官方管理器](https://github.com/Baka-SU/BakaSU/actions/runs/45221593387)。
- **SuSFS 升级与兼容**：内核侧已升级至官方 **SuSFS v2.4.0**（`f98f082`），原生匹配 BakaSU `57b2db60` 拆分后的 `selinux_hide` 模块并显式开启 `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y`；保留选择性 SELinux 隐藏补丁与 `open_redirect` 伪装，继续禁用 `preinit/runner.elf`（`-DKSU_NO_PREINIT` 同步覆盖 `fs/exec.c`）。
- **验证状态**：`6.6.162` + SuSFS v2.4.0 + BakaSU `57b2db60` 本地干净全量构建、ARM64 / LZ4 Legacy 魔数校验、冻结 GKI `.stg` 校验（3,264/3,267 一致，仅 3 项已知 `ZSTD_*` 固有差异；`abi_gki_aarch64_xiaomi` 641/641 符号命中）与 10,815 项基线校验均已通过；**本次组合尚待实机刷入验证**（上一版 `6.6.144` 已在 Rodin 实机验证开机、管理器识别与已安装模块运行）。
- **网络栈与内存机制硬锁**：内核层硬锁定 **BBRv3** 拥塞控制与 **FQ** 队列调度（拦截 userspace 覆写），并在 `mm/vmscan.c` 硬锁 **MGLRU** 核心位（防止小米 `init.rc` 因缺失私有 SmartCache 而关闭 MGLRU 导致空闲内存流失）。
- **ABI 保护机制**：`scripts/abi-guard.py` 在每次构建后比对 `docs/abi-baseline.json` 中 10,815 个内核类型大小（并支持 `--use-stg` 对照冻结 GKI `.stg` 快照），任何冻结结构体布局变化立即拦截。闭源厂商模块按固定布局编译，内核又不会拒绝 CRC 不匹配的模块，所以这项检查是刷机前的必需步骤。

### 已合入的上游 Backport

早期基于 6.6.144 合入的 17 个 backport 中，已有 **6 个**随本次 AOSP `android15-6.6-lts`（6.6.162）合并被上游原生吸收，其余 **11 个**继续作为本地 backport 保留。验证范围以各次构建与实机测试记录为准，不将编译通过等同于独立 A/B 验证。

**仍保留的本地 Backport（11 个）**

*调度（`sched/fair`）*
- `sched/fair: Allow decaying util_est when util_avg > CPU capa`
- `sched/fair: Fix initial util_avg calculation`
- `sched/fair: Don't trigger active lb if src_rq->curr is not on_rq`
- `sched/fair: Don't double balance_interval for migrate_misfit`
- `sched/fair: Do strict inequality check for busiest misfit task group`
- `sched/fair: Filter false overloaded_group case for EAS`
- `sched/fair: optimize the PLACE_LAG when se->vlag is zero`
- `sched/fair: Update overutilized detection`
- `sched/balance: Skip unnecessary updates to idle load balancer's flags`

*调度 / 空闲*
- `sched: idle: Optimize the generic idle loop by removing needless memory barrier`

*调频*（本机不生效：实际调频器为 MTK 的 `cpufreq_sugov_ext` 模块）
- `cpufreq/sched: Explicitly synchronize limits_changed flag handling`

**已由 AOSP 6.6.162 上游原生包含的原本地 Backport（6 个）**
- `sched/fair: Fix cpu_util runnable_avg arithmetic`（6.6.145）
- `sched/fair: Only update stats for allowed CPUs when looking for dst group`（6.6.145）
- `sched/fair: Fix overflow in update_tg_cfs_runnable()`（6.6.157）
- `sched/fair: Check CPU capacity before comparing group types during load balance`（6.6.157）
- `mm/migrate: report RCU-tasks quiescent states in migrate_pages_batch()`（6.6.157）
- `net/sched: fq: add overflow bounds to quantum and initial quantum`（6.6.160）

后续补丁将继续严格遵循“单 patch 审计 → 最小修改 → 本地构建 → ABI 校验 →
实机测试”流程逐个推进。

## 支持设备

| 设备 | 代号 | 系统 |
|---|---|---|
| Redmi Turbo 4 | rodin | HyperOS 3（Android 16） |
| POCO X7 Pro | rodin | HyperOS 3（Android 16） |

> **说明：** 未在 POCO 实机上测试过，但大概率可用——小米在 POCO 与 Redmi 机型上使用同一套内核源码。遇到问题欢迎带日志开 issue，我会尝试修复。

## 分支

- [`bsp-rodin-v-oss-bp`](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/tree/bsp-rodin-v-oss-bp) — 主构建分支，在小米官方 rodin 源码基础上叠加反向移植与增强

## 计划

- 适配 HyperOS 4

## 下载与支持

- [一些构建经验](BUILD-GUIDE.md)
- 预编译镜像：[Releases](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/releases)
- 问题反馈：请携带内核日志开 [issue](https://github.com/server0608/Xiaomi_Rodin_Kernel_Enhance/issues)
- 如果你觉得这个项目不错，欢迎点个 Star 支持我！

## 致谢

- [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance) — 初始仓库与增强特性维护者（原作者）
- [MiCode/Xiaomi_Kernel_OpenSource](https://github.com/MiCode/Xiaomi_Kernel_OpenSource) — rodin 官方内核源码（`bsp-rodin-v-oss`）
- [BakaSU](https://github.com/Baka-SU/BakaSU) / [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) / [SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) / [KernelSU](https://github.com/tiann/KernelSU) — Root 方案
- [SusFS](https://gitlab.com/simonpunk/susfs4ksu) — Root 隐藏
- [Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) — 防格机
- [Linux-Patches](https://gitlab.com/xanmod/linux-patches) — BBRv3 补丁
- AOSP `android15-6.6` / 上游 Linux 6.6 LTS

## 许可证

本仓库遵循 **GPL-2.0**，与 Linux 内核及其上游源码保持一致，详见 [LICENSES](LICENSES)。
