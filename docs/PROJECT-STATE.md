# 项目状态台账

> 最后更新：2026-11-08
> 本文件记录**客观事实**（版本、提交、配置），决策理由见
> [`PATCH-AUDIT.md`](PATCH-AUDIT.md)，硬约束见 [`../AGENTS.md`](../AGENTS.md)。

## 1. 版本与基线

| 项 | 值 |
|---|---|
| 设备 | Redmi Turbo 4 / POCO X7 Pro，代号 `rodin` |
| 系统 | HyperOS 3（**Android 16**） |
| GKI 世代 | `android15-6.6`（命名指内核分支，非设备 Android 版本） |
| 内核版本 | **6.6.144** |
| AOSP 基线 | `android15-6.6-lts`，**同为 6.6.144** |
| 落后 AOSP | **0 个提交** |
| kernel.org LTS 最新 | 6.6.162（领先 18 个版本，**不整体合并**） |
| 当前 HEAD | `5b2a89a1fae0`（已推送 origin） |

AOSP 尚未推进到 6.6.145+，因此我们与官方基线严格同步。若需新修复，
采用**精选 cherry-pick**，不整体合并。

## 2. 调度 backport 清单

### 2.1 已提交（9 个）

| # | 上游 commit | 内容 | 本地提交 |
|---|---|---|---|
| 1 | `29922fdfc2a4` | Fix `cpu_util` runnable_avg arithmetic | `2659273a6b5d` |
| 2 | `f2d650618bc7` | Allow decaying util_est when util_avg > CPU capa | `5fe9e53df79a` |
| 3 | `4f166adb5cb0` | Fix overflow in `update_tg_cfs_runnable()` | `fc4e76ae3b8b` |
| 4 | `72bffbf57c52` | Fix initial util_avg calculation | `86c172962385` |
| 5 | `cdd9e37ed46a` | Don't trigger active lb if `src_rq->curr` is not on_rq | `83e09dcf6bc6` |
| 6 | `50b101f6e586` | Check CPU capacity before comparing group types | `34849521a42a` |
| 7 | `58eeb2d79b54` | Don't double `balance_interval` for `migrate_misfit` | `3ae9af4f0507` |
| 8 | `7f1a7229718d` | Do strict inequality check for busiest misfit group | `b1b38d3f725e` |
| 9 | `d3d663faa1d4` | Filter false `overloaded_group` case for EAS | `f181620517e1` |

### 2.2 已实机验证通过（8 个）

| # | 上游 commit | 内容 | 方向 |
|---|---|---|---|
| 10 | `79443a7e9da3` | schedutil `limits_changed` 内存屏障同步 | 调度 |
| 11 | `82d6e01a0699` | 唤醒选核按 `p->cpus_ptr` 统计 | 调度 |
| 12 | `4423af84b297` | `place_entity()` 在 `vlag==0` 时短路 | 调度 |
| 13 | `926475806606` | `cpu_overutilized()` 去掉多余 `uclamp_min` 读取 | 调度 |
| 15 | `709f34f7c28d` | FQ `quantum` 溢出上界 | 网络 |
| 16 | `efe8f86c0916` | `migrate_pages_batch()` 报告 Tasks-RCU 静默态 | 内存 |

**来自 6.18 的精选**（同批验证，单独提交）：

| # | 上游 commit | 内容 | 方向 |
|---|---|---|---|
| 18 | `8e113df990c9` | 移除 `do_idle()` 中无用的 `rmb()` | 调度/空闲 |
| 19 | `f90cc919f9e5` | `kick_ilb()` 跳过已置位的 NOHZ 工作项 | 调度/均衡 |

改动文件：`kernel/sched/fair.c`、`kernel/sched/idle.c`、
`kernel/sched/cpufreq_schedutil.c`、`mm/migrate.c`、`net/sched/sch_fq.c`。
**全部为函数体内改动，ABI 未变**（`scripts/abi-guard.py` 验证 10783 个类型全匹配）。

**验证状态**

- 2026-11-08：6 补丁版（`1307`）与 8 补丁版（`2326`）均刷入 Redmi Turbo 4
  （rodin）**成功开机**。
- 最新产物：
  `out/AnyKernel3-Rodin-6.6.144-403Forbidden-840894-g8d7f2cae57bd-dirty-20261108-2326.zip`
- 用户主观反馈：响应性能感觉不错。**这是主观感受，不是测量数据**——
  没有帧率、调度延迟或频率驻留的 A/B 对照，因此**不得对外宣称性能提升**。
- Root 管理器识别、模块加载、长期功耗与待机电流尚待确认。

该构建的类型基线已固化到 `docs/abi-baseline.json`（10783 个类型），
作为后续所有构建的 ABI 对照基准。

### 2.3 已回退（详见 PATCH-AUDIT）

| 项 | 原因 |
|---|---|
| `CONFIG_READ_ONLY_THP_FOR_FS=y` | 给 `struct address_space` 加字段，破坏冻结 ABI，**实机变砖** |
| MGLRU `lru_gen_use_mm()` 改动 | 来源为未合入的 RFC，保守策略下暂缓 |

## 3. 已明确拒绝的补丁

| 上游 commit | 内容 | 拒绝理由 |
|---|---|---|
| `6d71a9c61604` | EEVDF 放置重构 | 需给 `struct sched_entity` 加 `rel_deadline` 字段 → **破坏 KMI** |
| `c70fc32f4443` | place_entity 约束 | 依赖上一条，连带拒绝 |
| `3167b620815c` | 拒绝 misfit 迁移到忙碌 SMT 兄弟 | arm64 无 SMT，`sched_smt_active()` 恒假，零收益 |
| `aa436b021e50` | schedutil rate limit 溢出 | 仅 32 位 `unsigned long` 溢出，arm64 为 64 位，无效 |

## 4. 网络栈硬锁

| 项 | 实现 |
|---|---|
| 默认拥塞控制 | **BBRv3**，`net/ipv4/sysctl_net_ipv4.c` sysctl 白名单 |
| 默认队列调度 | **FQ**，`net/core/sysctl_net_core.c` 的 `set_default_qdisc()` |
| 本地提交 | `5029f1d845df` |
| 目的 | 拦截 Android userspace（`init.rc`）对 sysctl 的覆写 |

相关待评估：`fd63409b669f`（`net/sched: fq: add overflow bounds to quantum`）——
超大 MTU 导致 `quantum == 0` 进而 `fq_dequeue()` 死循环。属健壮性修复，
非性能项，尚未纳入。

## 5. Root 方案（BakaSU + SuSFS）

| 项 | 值 |
|---|---|
| 内核模块 | BakaSU（ReSukiSU 分支），commit `516d3e87` |
| 版本号 | **35257**，UAPI 6 |
| SuSFS | 2.3.0 |
| 关键编译开关 | `-DKSU_NO_PREINIT`（**不可移除**） |
| 宏定义位置 | `tools/code_generation/code_generation.mk`、`tools/code_generation/preinit_runner/preinit_runner.mk`、`.github/workflows/sync-resukisu.yml` |

### 已解决的三个问题

1. **preinit bootloop**（提交 `4d68693d1b80`）
   `preinit/runner.elf` 会在早期阶段劫持 `/system/bin/init`，
   在 HyperOS 上直接触发 bootloop。已禁用并写入 Makefile 与 CI 同步脚本。

2. **`.gitignore` 被同步覆盖**
   `sync-resukisu.yml` 用 `rsync -a --delete` 整体替换 `drivers/kernelsu/`，
   连上游的 `.gitignore` 一起覆盖，构建产物重新变成未跟踪文件。
   已在工作流第 6 步追加忽略规则（与 `-DKSU_NO_PREINIT` 同样的处理方式）。

3. **SELinux 链接错误**（提交 `7f52a0fce3a4`）
   BakaSU 的 `security_context_to_sid_with_policy()` 是 8 参数版本，
   SuSFS 调用点传 `NULL` 给未使用的输出指针。已在
   `drivers/kernelsu/feature/selinux_hide.c`、`security/selinux/hooks.c`、
   `selinuxfs.c`、`include/linux/ksu_susfs_compat.h` 中对齐签名与可见性。
   并由 `.github/scripts/ksu_susfs_compat.py` 在自动同步后保持。

## 6. CI / 发布

| 工作流 | 触发 | 作用 |
|---|---|---|
| `sync-android15-6.6-lts.yml` | 每日 02:30 UTC+8 | 合并 AOSP ACK 基线 |
| `sync-resukisu.yml` | 每日 02:50 UTC+8 | 同步 BakaSU 并保持兼容修复 |
| `build-kernel.yml` | 每日 03:15 UTC+8 + 手动 | 构建、打包、发 Release |

**管理器版本锁定**：CI 只打包与内核模块**同一提交**的官方 manager APK，
避免版本错配。伪装版仅在当次上游构建提供时附带。

Release 命名：`v6.6.144-<BUILD_USER>-g<short-sha>-<YYYYMMDD-HHMM>`

## 7. 构建

```bash
./build-local.sh
```

- 工具链：`/home/server0608/toolchains/clang-r596125`
- 配置：**只能** `make gki_defconfig`（不要 defconfig + gki_defconfig 组合）
- 耗时：增量约 1.5 分钟
- 魔数：`Image` @0x38 = `41 52 4d 64`；`Image.lz4` = `02 21 4c 18`
- 产物：`out/AnyKernel3-Rodin-*.zip`（只含 `Image`，`block=boot`）

## 8. 与 AOSP 的差异面

`kernel/sched/` 下相对 `android15-6.6-lts` 仅 4 个文件不同，全部可解释：

| 文件 | 差异 | 对应 |
|---|---|---|
| `vendor_hooks.c` | +1 行 `EXPORT_TRACEPOINT_SYMBOL_GPL(android_vh_set_sugov_sched_attr)` | MTK 原厂调频钩子 |
| `cpufreq_schedutil.c` | +24/−4 | 补丁 10 |
| `idle.c` | −2 | 补丁 18 |
| `fair.c` | +81/−43 | 补丁 1–9、11、12、13、19 |

`kernel/sched/` 之外的补丁：

| 文件 | 改动 | 补丁 |
|---|---|---|
| `mm/migrate.c` | +1/−1 | 16 |
| `net/sched/sch_fq.c` | +4/−2 | 15 |

**无任何意外改动。** 这是判断是否误改的重要基线。

> `fair.c` 的 +81/−43 中绝大部分是 2026-11 之前已发布的 9 个补丁。
> 2026-11-08 这一批的实际增量（相对上一发布提交 `a9896306cb5b`）：
>
> ```
> cpufreq_schedutil.c  +24 / -4
> fair.c               +11 / -5
> idle.c                +0 / -2
> mm/migrate.c          +1 / -1
> sch_fq.c              +4 / -2
> 合计                 +40 / -14
> ```

## 9. 待办

- [x] 8 个补丁实机验证（2026-11-08 两批均开机成功）
- [x] 分成独立提交（保留上游 commit 溯源）
- [ ] 长期观察：待机电流、唤醒响应、Root/模块/相机/充电/指纹
- [ ] 从设备拉取厂商 `.ko`，跑一次完整 CRC 基线，建立出厂 ABI 指纹
- [ ] 补齐中文 README 的 backport 数量（当前写的是 9 个，实际 17 个）

## 10. 每次刷机前的强制检查

```bash
scripts/abi-guard.py     # ABI 类型大小是否与已验证构建一致（退出码必须为 0）
od -An -tx1 -j56 -N4 arch/arm64/boot/Image      # 41 52 4d 64
od -An -tx1 -N4 arch/arm64/boot/Image.lz4       # 02 21 4c 18
```

## 11. 已知不可做（避免重复调研）

| 候选 | 原因 |
|---|---|
| `CONFIG_READ_ONLY_THP_FOR_FS=y` | 改 `address_space` 布局，**已致实机变砖** |
| `6d71a9c61604` EEVDF 放置重构 | 需给 `sched_entity` 加字段，破坏 KMI |
| `570c8efd5eb7` sched/psi 优化 | 改 `psi_group_cpu`，在冻结 ABI 中 |
| `90ca9410dab2` uclamp 对齐 | 依赖 6.8+ 的 `sched_delayed` / `ENQUEUE_DELAYED` |
| `d34e798094ca` can_migrate_task 重构 | 依赖 6.8+ 的 `cpumask_first_and_and()` |
| EAS 能耗计算 O(N)→O(1) | 未进 mainline，无验证 |
| `mm/mglru` reclaim loop 重构（15 补丁） | 来自 6.18 世代 mm-stable，跨版本过多 |
| `mm: batch TLB flushing for dirty folios` | 2026-10 提案，未合入 |
| binder CTABS 启发式 | LKML 提案，未合入 |
| 关闭 `CONFIG_INIT_ON_ALLOC_DEFAULT_ON` | 能提速分配，但属 GKI 安全基线 |
| `writeback: Avoid contention on wb->list_lock` | 99 行，改 `struct bdi_writeback`，场景罕见 |
| 整体 merge kernel.org 6.6.162 / 升级 6.18 | 跨 KMI 世代，闭源模块无法加载 |
