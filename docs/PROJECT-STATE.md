# 项目状态台账

> 最后更新：2026-11-27
> 本文件记录**客观事实**（版本、提交、配置），决策理由见
> [`PATCH-AUDIT.md`](PATCH-AUDIT.md)，硬约束见 [`../AGENTS.md`](../AGENTS.md)。

## 1. 版本与基线

| 项 | 值 |
|---|---|
| 设备 | Redmi Turbo 4 / POCO X7 Pro，代号 `rodin` |
| 系统 | HyperOS 3 / HyperOS 4（实测含 `OS4.0.0.15.XPTCNXM` / Android 17） |
| GKI 世代 | `android15-6.6`（命名指内核分支，非设备 Android 版本） |
| 内核版本 | **6.6.144**（已实机验证稳定） |
| AOSP 合并基线 | `android15-6.6-lts` @ `1c39bb5f635a`（本地合并提交 `76219f706bf4`） |
| 上游状态 | AOSP `android15-6.6-lts` 已推进至 `6.6.162` / `6.6.163`，因整机死机回归暂隔离于实验分支 `exp/6.6.162-susfs24`（见 §9.7） |
| 稳定回退基线 | `7a6714fea2d9`（内核源码等同已稳跑 36h+ 的 `fc96916230e9`） |

当前主分支 `bsp-rodin-v-oss-bp` 固定在已验证稳定的 **6.6.144 + BakaSU `7b65bde0` + SuSFS `v2.3.0`**，
并将 `6.6.162/6.6.163 + SuSFS v2.4.0 + BakaSU 57b2db60/cac1e793` 完整保留在
`exp/6.6.162-susfs24`（`cfa5202c04bb`）待后续隔离排查。

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
| 内核模块 | BakaSU（ReSukiSU 分支），commit `7b65bde0`（`KSU_LOCAL_VERSION = 4562`） |
| 版本号 | **35262**，UAPI 6 |
| SuSFS | 2.3.0 |
| 关键编译开关 | `-DKSU_NO_PREINIT`（**不可移除**） |
| 宏定义位置 | `tools/code_generation/code_generation.mk`、`tools/code_generation/preinit_runner/preinit_runner.mk`、`fs/Makefile`、`.github/workflows/sync-resukisu.yml` |

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
| `sync-android15-6.6-lts.yml` | 仅手动 `workflow_dispatch`（定时 `37 18 * * *` 已暂停） | 合并 AOSP ACK 基线 |
| `sync-resukisu.yml` | 仅手动 `workflow_dispatch`（定时 `53 18 * * *` 已暂停） | 同步 BakaSU 并保持兼容修复 |
| `build-kernel.yml` | 手动 `workflow_dispatch` + `workflow_run`（定时 `19 19 * * *` 已暂停） | 构建、打包、发 Release |

> **2026-11-27 定时调度暂停说明**：因 `6.6.162 + SuSFS v2.4.0 + BakaSU 57b2db60` 升级批次触发整机死机/看门狗复位（见 §9.7），已将实验历史另存到 `exp/6.6.162-susfs24` 并将主分支回退到稳定 `6.6.144`（`7a6714fea2d9`）。三个工作流的 `schedule` 均已暂停，防止夜间自动合并 `6.6.162+`、拉取不匹配 SuSFS v2.3.0 的新版 BakaSU 或自动发包；手动 `workflow_dispatch` 仍可用。

> **2026-11-24 定时调度修复**：三个工作流自 2026-11-09 起 `schedule` 静默停摆（状态仍显示 `active`，手动 `workflow_dispatch` 正常），与 11-08 `sync-resukisu.yml` 解析失败及 11-09 18:07–19:20 UTC GitHub Actions 核心数据库迁移故障窗口完全重合。已将三个 `cron` 改为非整点奇数分钟并推送到默认分支，同时通过 GitHub API 执行 `disable` → `enable` 强制重新注册定时调度。

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

## 9.5 实机功耗排查记录（2026-11-09）

用户反馈续航明显下降。用 ADB 采集数据后的结论：

### 关键测量

| 指标 | 值 | 判读 |
|---|---|---|
| 息屏待机电流 | 59–78 mA | 正常（约 1.1%/h） |
| 放电构成 | 亮屏 **52%** / 息屏 7% / Doze 1% | 问题在亮屏使用 |
| Doze 累计 | 4.5h 内仅 6m50s | Doze 几乎不进入 |
| 换出总量 | 17.1M 页 ≈ 68 GB | 内存压力大，但换出已停止 |

### 根因：Scene（`com.omarea.vtools`）的高性能调度

`scene-daemon` 以 root 常驻，`profile.json` 的 limiter 直接锁高频下限：

```json
"p2": { "cpus": [
  { "max": 2100000, "min": 1800000 },
  { "max": 2600000, "min": 2100000 },
  { "max": 2800000, "min": 2100000 } ] }
```

scheme 同时抬高上限：`performance` = 2.1/2.8/3.0 GHz，
`fast` 更高。并通过 `/proc/easmgr/eas_ioctl` 写 EAS 边距。

实测抓到：`policy4 min=2200000 cur=2800000`，息屏状态下
电流飙到 1.0–2.6 A；静置 60 秒后回到 700 MHz。

**结论：与内核补丁无关。** 这是用户态调度工具的行为。

### 附带纠正：补丁 10 在本机不生效

实际调频器是 MTK 的 `cpufreq_sugov_ext` 模块，不是树内 `schedutil`。
详见 [`PATCH-AUDIT.md`](PATCH-AUDIT.md) 补丁 10。

### 可复用的排查方法

```bash
# 真实电流（注意：mt6375-gauge/current_now 是无效值）
adb shell su -c 'cat /sys/class/power_supply/battery/current_now'   # uA

# 是否被锁高频
for p in policy0 policy4 policy7; do
  adb shell "cat /sys/devices/system/cpu/cpufreq/$p/scaling_min_freq"
done

# 放电构成
adb shell "dumpsys batterystats --charged | grep -E 'Amount discharged'"

# 采样时必须静置，adb 命令本身会唤醒设备并触发 boost
```

## 9.6 MGLRU 被禁用（2026-11-09 发现并修复）

### 现象

`kswapd0` 在 top 中一度占到 39% CPU，空闲内存持续流失到 100–130 MB。

### 根因：小米 SmartCache 缺失导致两边落空

```
/vendor/etc/init/hw/init.mt6899.rc   (MTK)
    write /sys/kernel/mm/lru_gen/enabled y      ← MTK 想启用 MGLRU

/system/etc/init/hw/init.rc          (小米)
    on property:persist.sys.stability.SmartCacheEnable=true
        write /sys/kernel/mm/lru_gen/enabled 0  ← 关掉 MGLRU，让位给 SmartCache
```

但 **SmartCache 是小米私有内核补丁**（`/sys/kernel/smart_cache/*`、
`/dev/memcg/memory.mctrl.*`），既不在 AOSP 基线里，**也不在本仓库的树里**：

```bash
$ ls /sys/kernel/smart_cache
No such file or directory
$ grep -rn smart_cache --include='*.c' .
（无结果）
```

结果：MGLRU 被关，SmartCache 又不存在 → **退回老式 LRU**。

### 修复

```bash
adb shell su -c 'setprop persist.sys.stability.SmartCacheEnable false'   # 重启后生效
adb shell su -c 'echo 7 > /sys/kernel/mm/lru_gen/enabled'                # 立即生效
```

运行时值应为 `0x0003`（MM_WALK | NONLEAF）。

### 实测效果（各 120 秒）

| | kswapd0 CPU | MemFree |
|---|---|---|
| MGLRU 关 | 0.4% | 350 → **101 MB**（流失） |
| MGLRU 开 | 0.8% | 172 → **194 MB**（稳住） |

**结论**：MGLRU 的作用是让空闲内存不再持续流失，代价是 kswapd 多做约
0.4% 的 CPU。**不能据此宣称省电**；它的价值在于内存稳定性。

### 内核级硬锁

仅靠属性不够——系统更新或恢复出厂可能重置 `persist.*`。因此在
`mm/vmscan.c` 的 `enabled_store()` 中拒绝清除 `LRU_GEN_CORE`：

```c
if (!(caps & BIT(LRU_GEN_CORE))) {
        pr_info("lru_gen: keeping MGLRU enabled, ignoring request for caps 0x%x\n",
                caps);
        return len;
}
```

只拦核心算法，`MM_WALK` / `NONLEAF_YOUNG` 等可选位仍可单独开关。

验证：

```bash
adb shell su -c 'echo 0 > /sys/kernel/mm/lru_gen/enabled'
adb shell su -c 'cat /sys/kernel/mm/lru_gen/enabled'   # 仍应为 0x0003
adb shell su -c 'dmesg | grep "keeping MGLRU"'
```

### 教训

小米原厂内核可能带有树内没有的私有特性，而 userspace 的 init.rc 会据此
关闭标准机制。遇到异常行为时，应比对 init.rc 的写入与本内核实际提供的
sysfs 节点。

## 9.7 6.6.162 + SuSFS v2.4.0 / BakaSU 57b2db60 整机死机回归记录（2026-11-27）

### 现象与基线对照

- **故障版本**：`6.6.162`（合并 `aosp/android15-6.6-lts` @ `8e5968bb7aca`）+ SuSFS v2.4.0（`f98f082`）+ BakaSU `57b2db60`（`35285`），现已完整隔离至分支 `exp/6.6.162-susfs24`（含次日夜间自动同步的 `6.6.163` / `cac1e793` 提交 `cfa5202c04bb`）。
- **实机症状**（`rodin` / `OS4.0.0.15.XPTCNXM` / Android 17）：
  - 启动相机后 **20–40 秒**稳定复现整机卡死，待机约 4 分钟偶发同样卡死；
  - 现场采样（`live2/heartbeat.log`）记录到启动相机后 7 秒内 swap 暴涨 **+380 MB**（880 MB → 1260 MB）、最高温飙至 **95°C**（`94999`）、`procs_blocked=0`，随后彻底断联并由 MTK AP watchdog 触发硬复位（`aee_aed.pureason=RebootException` / `aee_aed.poffreason=Cold_reset`）；
  - `pstore` / `ramoops` 为空，无 kernel oops/panic。
- **对照验证**：`6.6.144`（`fc96916230e9`）此前连续稳定运行 **36 小时以上**（正常关机 `[129642s]`）；2026-11-27 实机刷回 `6.6.144` 后已恢复稳定。

### 现场日志盲区（后续排查须避坑）

1. `cat /dev/kmsg` 会从开机历史最旧条目开始倒灌，断联时日志仅追到 `up=96s`，错过了死机前最后 114 秒（`up=210s`）；后续实机抓日志必须改用 `dmesg -w`（跳过历史）。
2. `CONFIG_HARDLOCKUP_DETECTOR` 未启用；cmdline 含 `nosoftlockup` 导致运行时 `watchdog=0`；`hung_task`（60s）仅检测 `D` 态进程，对 `procs_blocked=0` 的可运行态死循环或关中断死锁完全失明。

### 已排除方向（离线验证）

- **厂商模块 ABI / CRC 漂移（排除）**：274 个 `/vendor/lib/modules/*.ko` 均基于 `6.6.77` 编译。对比 `6.6.144` 与 `6.6.162` 产出的 `vmlinux.symvers`，5 个核心厂商模块（`mali_kbase_mt6899_r49`、`scheduler`、`mtk_c2ps`、`task_turbo`、`fpsgo`）的 CRC 差异集合完全一致；16,727 个公共导出符号仅 55 个变动，零个涉及 sched/UFS/Mali/IOMMU/thermal/cpufreq/camera。
- **核心结构体布局漂移（排除）**：`pahole --sizes` 确认 `task_struct`、`rq`（`CONFIG_SCHED_CORE` 未启用）、`cfs_rq`、`sched_entity`、`page`、`mm_struct` 尺寸与 `6.6.144` 一致。
- **合并冲突与 `priority_uid_filter` RCU 怀疑（排除）**：复核 `bf641bbe26e9` 冲突文件（含 `ufs-mcq.c`、`mm/vmscan.c`、`fair.c`、`cpufreq_schedutil.c`）均正常；`susfs_is_priority_uid_filtered()` 全部 4 处调用均在 `rcu_read_lock()` 内。

### 静态审计定位的两条独立嫌疑线

- **嫌疑线 A（`6.6.144 → 6.6.162` LTS / 小米 GKI）**：
  1. `arch/arm64/mm/fault.c` 新增导出到 `abi_gki_aarch64_xiaomi` 的 per-VMA-lock 缺页钩子（`3cf00dca4aad` / `8a74f0885234`），包含无上限的 `if (vma_retry) goto lock_vma;` 重试循环；需在设备连上 ADB 时扫描全部 274 个 `/vendor/lib/modules/*.ko` 确认是否有模块绑定。
  2. `mm/vmscan.c` revert `4fbde4d4c15f` 并新增 5 个回收 vendor hooks；`CONFIG_ARM64_ERRATUM_3821522=y` 命中 Cortex-A725 并关闭 AMU 频率不变性；`kernel/futex/core.c` 修改 `handle_futex_death()`。
- **嫌疑线 B（SuSFS v2.4.0 + BakaSU `57b2db60`，已实锤多项代码缺陷）**：
  1. **CRITICAL**：`fs/susfs.c` 中 `watch_one_dir()` 出错路径 `path_put(&wd->kpath)` 后未清零，`susfs_sdcard_cleanup_fn()` 再次 `path_put()`（双重释放）。
  2. **CRITICAL**：`fs/namespace.c` 中 `susfs_get_non_sus_vfsmnt_from_vfsmnt()` 异常分支未持引用返回 `vfsmnt`，而 `fs/statfs.c` 与 `fs/susfs.c` 调用方无条件 `dput()`/`mntput()`。
  3. **HIGH**：`fs/susfs.c` 移除 `susfs_is_inode_sus_path()` 外层 `umounted` 门控并默认开启日志；`fs/statfs.c` 未对 `d_backing_inode()` 判空。
  4. **HIGH**：`fs/notify/fdinfo.c` 在持有 `group->mark_mutex` 期间执行 `GFP_KERNEL`、`d_path()` 与 `kern_path()`（存在锁序反转风险）。
  5. **HIGH**：`fs/susfs.c` 中 `SUS_TYPE_HLIST` 未存 `type_value` 导致哈希碰撞误隐藏正常 SELinux 类型；`selinux_hide` 持双互斥锁调用 `stop_machine()`、`fake_status` 页缺引用计数，且新增 `susfs_selinux_inode_setxattr()` 接管 `setxattr`。

### 后续恢复排查入口（暂缓，按需重启）

1. 先只读 ADB 扫描 274 个 `/vendor/lib/modules/*.ko` 是否引用上述 7 个新增 vendor hooks，确认嫌疑线 A1。
2. 刷入已离线编译的纯合并二分包（`04feff837145`：`6.6.162` + 旧稳定 SuSFS v2.3.0 / BakaSU `7b65bde0`，免换管理器）测相机 1 分钟，一步分清锅在 A 还是 B。
3. 无论二分结果如何，合入 SuSFS v2.4.0 前必须先修复嫌疑线 B 已实锤缺陷；若需在内核抓栈，临时调试包开启 `CONFIG_PROVE_LOCKING=y`、`CONFIG_DEBUG_ATOMIC_SLEEP=y`、`CONFIG_HARDLOCKUP_DETECTOR=y` 并改用 `dmesg -w`。

## 10. 每次刷机前的强制检查

```bash
scripts/check-workflows.py   # 只在改了 .github/workflows/ 时需要
scripts/abi-guard.py         # ABI 类型大小是否与已验证构建一致（退出码必须为 0）
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
