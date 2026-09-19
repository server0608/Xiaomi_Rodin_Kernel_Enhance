# Xiaomi Rodin Kernel Enhance

[![Kernel](https://img.shields.io/badge/kernel-6.6.142_LTS-blue)](https://kernel.org)
[![Base](https://img.shields.io/badge/base-MiCode%20bsp--rodin--v--oss-orange)](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss)
[![Root](https://img.shields.io/badge/Root-ReSukiSU-green)](https://github.com/ReSukiSU/ReSukiSU)
[![SuSFS](https://img.shields.io/badge/Hiding-SuSFS-green)](https://gitlab.com/simonpunk/susfs4ksu)
[![License](https://img.shields.io/badge/license-GPL--2.0-lightgrey)](LICENSES)

简体中文 | [English](README.en.md)

基于小米已开源的 [`bsp-rodin-v-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/bsp-rodin-v-oss) 内核源码（AOSP `android15-6.6` GKI / 联发科）构建的 rodin 设备增强内核，并持续跟进最新 **6.6 LTS**。

> **说明：** 本项目 Fork 并修改自原作者仓库 [omajili-manbu/Xiaomi_Rodin_Kernel_Enhance](https://github.com/omajili-manbu/Xiaomi_Rodin_Kernel_Enhance)，感谢原作者的前期工作！

## 特性

### Root 与隐藏
- 内置 **ReSukiSU**，集成自 [`ReSukiSU/ReSukiSU`（`main`）](https://github.com/ReSukiSU/ReSukiSU/tree/main)
- 内置 **SuSFS**，集成自 [`omajili-manbu/susfs4ksu`（`gki-android15-6.6-mod`）](https://github.com/omajili-manbu/susfs4ksu/tree/gki-android15-6.6-mod)
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
- **CAKE 智能流调度**：内建 CAKE 队列规则，具备顶级流隔离与 Bufferbloat 抑制能力，大幅降低多任务高负载下的网络延迟与游戏卡顿
- **前台 I/O 延迟保护与写回节流**：启用 `BLK_CGROUP_IOLATENCY` 与 `BLK_WBT_MQ`，优先保障前台游戏与交互的闪存读写响应，防止后台下载刷盘导致掉帧
- **DAMON 物理内存监控与热度排序**：启用 `DAMON_PADDR`、`DAMON_RECLAIM` 与 `DAMON_LRU_SORT`，动态监控访问热度，保护活跃热页并分流冷页，提升后台保活与内存吞吐

### 稳定性修复
- 修复概率性开机卡死，恢复 vendor 模块兼容
- 在小米官方内核基础上反向移植上游修复

调优理念是**性能与续航兼顾**——所有提升均来自编译时优化、更新的内核、更新的算法，以及对小米官方内核的 bug 修复，没有偏向任何一方的激进调整。

## 当前稳定状态与最近更新

- **内核版本**：Linux 6.6.143 (Android 15 GKI)
- **目标平台**：Xiaomi Rodin / MT6897 (Dimensity 8400 Ultra)
- **稳定基线**：`34849521a42a`

### 已实机验证的调度器 Backport
以下 6 个 CFS 调度器补丁均已完成严格审计、源码移植、本地编译以及 Rodin 实机刷入测试：
- `sched/fair: Fix cpu_util runnable_avg arithmetic`
- `sched/fair: Allow decaying util_est when util_avg > CPU capa`
- `sched/fair: Fix overflow in update_tg_cfs_runnable()`
- `sched/fair: Fix initial util_avg calculation`
- `sched/fair: Don't trigger active lb if src_rq->curr is not on_rq`
- `sched/fair: Check CPU capacity before comparing group types during load balance`

后续调度器补丁将继续严格遵循“单 patch 审计 → 最小修改 → 本地构建 → 实机测试”流程逐个推进。

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
- [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) / [SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) / [KernelSU](https://github.com/tiann/KernelSU) — Root 方案
- [SusFS](https://gitlab.com/simonpunk/susfs4ksu) — Root 隐藏
- [Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) — 防格机
- [Linux-Patches](https://gitlab.com/xanmod/linux-patches) — BBRv3 补丁
- AOSP `android15-6.6` / 上游 Linux 6.6 LTS

## 许可证

本仓库遵循 **GPL-2.0**，与 Linux 内核及其上游源码保持一致，详见 [LICENSES](LICENSES)。
