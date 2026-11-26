# 项目状态台账

> 最后更新：2026-11-25
> 本文件记录**客观事实**（版本、提交、配置），决策理由见
> [`PATCH-AUDIT.md`](PATCH-AUDIT.md)，硬约束见 [`../AGENTS.md`](../AGENTS.md)。

## 1. 版本与基线

| 项 | 值 |
|---|---|
| 设备 | Redmi Turbo 4 / POCO X7 Pro，代号 `rodin` |
| 系统 | HyperOS 3（**Android 16**） |
| GKI 世代 | `android15-6.6`（命名指内核分支，非设备 Android 版本） |
| 内核版本 | **6.6.162** |
| AOSP 基线 | `android15-6.6-lts` @ `8e5968bb7aca`（**同为 6.6.162**） |
| 落后 AOSP | **0 个提交** |
| 合并提交 | `bf641bbe26e9`（2026-11-25 本地合并；当前工作区另含 SUSFS v2.4.0 + BakaSU `57b2db60` + `tcp_bbr3_compat.h` + CI 适配 + 基线刷新，待提交推送） |
| 远端 `origin` HEAD | `7a6714fea2d9`（含 2026-11-24 cron 定时调度修复） |

2026-11-25 已将 AOSP `android15-6.6-lts`（`8e5968bb7aca`，Linux `6.6.162`）合并到
`bsp-rodin-v-oss-bp`，解决唯一冲突 `drivers/ufs/core/ufs-mcq.c`（保留上游
`ufshcd_mcq_compl_cqe()` 与双参 `ufshcd_mcq_get_tag(hba, cqe)`，将 MTK debug
相关 `tag` 移入 `#if IS_ENABLED(CONFIG_MTK_UFS_DEBUG)`），并同步适配
`net/ipv4/tcp_bbr3_compat.h` 以匹配 6.6.162 新增的三参数 `__tcp_send_ack()`。
仍严格遵循**只合 AOSP ACK、不整体合并 kernel.org stable** 的原则。

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

改动文件（6.6.144 批次）：`kernel/sched/fair.c`、`kernel/sched/idle.c`、
`kernel/sched/cpufreq_schedutil.c`、`mm/migrate.c`、`net/sched/sch_fq.c`。
合并 AOSP 6.6.162（`8e5968bb7aca`）后，早期 17 个 backport 中有 **6 个**已被上游原生吸收
（#1、#11 于 6.6.145；#3、#6、#16 于 6.6.157；#15 于 6.6.160），其余 **11 个**继续作为本地 backport 保留。

**验证状态**

- 2026-11-08（6.6.144）：6 补丁版（`1307`）与 8 补丁版（`2326`）均刷入 Redmi Turbo 4
  （rodin）**成功开机**；旧基线记录 10,783 个类型。
- 2026-11-25（**6.6.162 + SuSFS v2.4.0 + BakaSU `57b2db60`**）：
  - 干净全量编译（`make ARCH=arm64 LLVM=1 clean` → `./build-local.sh`，耗时 3 分 23 秒）与打包通过；
  - 最新产物：`out/AnyKernel3-Rodin-6.6.162-403Forbidden-841169-gbf641bbe26e9-dirty-20261125-1155.zip`；
  - 魔数校验通过：`Image` @0x38 = `41 52 4d 64`，`Image.lz4` = `02 21 4c 18`；
  - 冻结 GKI ABI 校验（`scripts/abi-guard.py --use-stg`）：**3,264 / 3,267** 已构建类型匹配（仅 3 项已知固有的 `ZSTD_CCtx_params_s` / `ZSTD_CCtx_s` / `ZSTD_DCtx_s` 差异）；相对旧 6.6.144 基线变化的 45 个类型（41 个来自 AOSP 6.6.144→6.6.162 内部改动 + 4 个来自 SuSFS v2.4.0 私有结构体）中 **0 个位于冻结 `.stg`**；`android/abi_gki_aarch64_xiaomi` 的 **641 / 641** 符号全部导出于 `vmlinux.symvers`；
  - `docs/abi-baseline.json` 已刷新为 `6.6.162-403Forbidden-841169-gbf641bbe26e9-dirty`（**10,815 个类型**，`scripts/abi-guard.py` 退出码 `0`）；
  - **本 6.6.162 版本尚未刷机实测**，待实机验证开机、BakaSU 管理器、SuSFS v2.4.0 隐藏与日常稳定性。
- 用户此前对 6.6.144 的主观反馈（响应性能感觉不错）属于主观感受而非 A/B 测量数据，**不得对外宣称性能提升**。

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
| 默认拥塞控制 | **BBRv3**，`net/ipv4/sysctl_net_ipv4.c` sysctl 白名单（6.6.162 已同步更新 `net/ipv4/tcp_bbr3_compat.h` 适配三参数 `__tcp_send_ack()`） |
| 默认队列调度 | **FQ**，`net/core/sysctl_net_core.c` 的 `set_default_qdisc()` |
| 本地提交 | `5029f1d845df` |
| 目的 | 拦截 Android userspace（`init.rc`）对 sysctl 的覆写 |

注：`fd63409b669f`（`net/sched: fq: add overflow bounds to quantum`）已于补丁 15 合入，并已在 AOSP 6.6.160（含于当前 6.6.162 基线）中由上游原生包含。

## 5. Root 方案（BakaSU + SuSFS）

| 项 | 值 |
|---|---|
| 内核模块 | BakaSU（`ReSukiSU/ReSukiSU` `main`），commit `57b2db60`（tag `v4.2.0-rc3`，count `4585`） |
| 版本号 | **35285**，UAPI **6**（同提交官方 Build Manager Run `45221593387`） |
| SuSFS | 官方 `simonpunk/susfs4ksu` **v2.4.0**（`gki-android15-6.6` @ `f98f082`），叠加定制选择性隐藏补丁 `55`/`56` 与 `open_redirect` 伪装；`gki_defconfig` 显式开启 `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y` |
| 关键编译开关 | `-DKSU_NO_PREINIT`（**不可移除**） |
| 宏定义位置 | `drivers/kernelsu/tools/code_generation/code_generation.mk`、`drivers/kernelsu/tools/code_generation/preinit_runner/preinit_runner.mk`、`fs/Makefile`（`CFLAGS_exec.o += -DKSU_NO_PREINIT`）、`.github/workflows/sync-resukisu.yml` |

### 已解决的四个问题

1. **preinit bootloop**（提交 `4d68693d1b80` + 2026-11-25 补齐 `fs/Makefile`）
   `preinit/runner.elf` 会在早期阶段劫持 `/system/bin/init`，
   在 HyperOS 上直接触发 bootloop。已在 `drivers/kernelsu`、CI 同步脚本及
   `fs/Makefile`（覆盖 SuSFS v2.4.0 在 `fs/exec.c` 中的 `#ifndef KSU_NO_PREINIT` 守卫）中全面禁用。

2. **`.gitignore` 被同步覆盖**
   `sync-resukisu.yml` 用 `rsync -a --delete` 整体替换 `drivers/kernelsu/`，
   连上游的 `.gitignore` 一起覆盖，构建产物重新变成未跟踪文件。
   已在工作流同步步骤重新追加忽略规则（与 `-DKSU_NO_PREINIT` 同样的处理方式）。

3. **升级至 SuSFS v2.4.0 并适配 BakaSU `57b2db60` 的 `selinux_hide` 拆分**（2026-11-25）
   早期 `7f52a0fce3a4` 为兼容 SuSFS 2.3.0 与旧版单文件 `selinux_hide.c` 维护了
   `include/linux/ksu_susfs_compat.h` 垫片；上游 `57b2db60` 将 `selinux_hide` 拆分为
   `feature/selinux_hide/{selinux_hide.c, selinux_hide.h, selinux_hide_auto.c, selinux_hide_susfs.c}`
   并原生要求 SuSFS v2.4.0 符号。现已将内核侧 27 个文件全量升级至官方 SuSFS v2.4.0（保留
   `55`/`56` 选择性 SELinux 隐藏补丁与 `open_redirect` 伪装），移除废弃的
   `include/linux/ksu_susfs_compat.h`，并将 `.github/scripts/ksu_susfs_compat.py`
   重写为只读接口契约校验器。

4. **修复 `ksu_pin_version.py` 应对上游 Kbuild 重排**（2026-11-25）
   BakaSU `57b2db60` 将 `KSU_TAG_NAME` / `KSU_COMMIT_SHA` / `KSU_BRANCH_NAME` 移至
   `KSU_VERSION` 之后，旧脚本单锚点匹配会遗漏 git 查询行。现已改为多锚点取最大结束位置，
   并增加防 `$(GIT_BIN)` 泄漏断言。

## 6. CI / 发布

| 工作流 | 触发 | 作用 |
|---|---|---|
| `sync-android15-6.6-lts.yml` | 每日 02:37 UTC+8 (`37 18 * * *`) | 合并 AOSP ACK 基线 |
| `sync-resukisu.yml` | 每日 02:53 UTC+8 (`53 18 * * *`) | 同步 BakaSU 并保持兼容修复 |
| `build-kernel.yml` | 每日 03:19 UTC+8 (`19 19 * * *`) + `workflow_run` + 手动 | 构建、打包、发 Release |

> **2026-11-24 – 11-25 定时调度与失败路径修复**：三个工作流自 2026-11-09 起 `schedule` 静默停摆（状态仍显示 `active`，手动 `workflow_dispatch` 正常），与 11-08 `sync-resukisu.yml` 解析失败及 11-09 18:07–19:20 UTC GitHub Actions 核心数据库迁移故障窗口完全重合。已将三个 `cron` 改为非整点奇数分钟并推送到默认分支，同时通过 GitHub API 执行 `disable` → `enable` 强制重新注册定时调度；**2026-11-25 已实测全部 3 条 `schedule` 恢复触发**（`build-kernel` Run `45537371348` 成功）。另外为 `sync-android15-6.6-lts.yml` 与 `sync-resukisu.yml` 的 `gh issue create` 增加了仓库 `has_issues` 检查，避免关闭 Issues 时二次报错。

**管理器版本锁定**：CI 只打包与内核模块**同一提交**的官方 manager APK，
避免版本错配。伪装版仅在当次上游构建提供时附带。

Release 命名：`v<KERNEL_RELEASE>-<YYYYMMDD-HHMM>`（例：`v6.6.162-<BUILD_USER>-g<short-sha>-<YYYYMMDD-HHMM>`）

## 7. 构建

```bash
./build-local.sh
```

- 工具链：`/home/server0608/toolchains/clang-r596125`
- 配置：**只能** `make gki_defconfig`（不要 defconfig + gki_defconfig 组合）
- 耗时：增量约 1.5 分钟，干净全量约 3.5 分钟（切换 AOSP AFDO profile 后必须先 `make ARCH=arm64 LLVM=1 clean` 避免 ThinLTO `ProfileSummary` 冲突）
- 魔数：`Image` @0x38 = `41 52 4d 64`；`Image.lz4` = `02 21 4c 18`
- 产物：`out/AnyKernel3-Rodin-*.zip`（只含 `Image`，`block=boot`）

## 8. 与 AOSP 的差异面

相对当前 AOSP `android15-6.6-lts`（`8e5968bb7aca`，6.6.162），`kernel/sched/` 下仅 4 个文件不同，全部可解释：

| 文件 | 差异 | 对应 |
|---|---|---|
| `vendor_hooks.c` | +1 行 `EXPORT_TRACEPOINT_SYMBOL_GPL(android_vh_set_sugov_sched_attr)` | MTK 原厂调频钩子 |
| `cpufreq_schedutil.c` | +24/−4 | 补丁 10（本机 MTK `cpufreq_sugov_ext` 下不生效） |
| `idle.c` | −2 | 补丁 18 |
| `fair.c` | +51/−21 | 仍保留的 9 个 `fair.c` 补丁（2、4、5、7、8、9、12、13、19；1、3、6、11 已被 6.6.162 原生包含） |

`kernel/sched/` 之外的调度/内存/网络补丁差异：

| 文件 | 改动 | 对应 |
|---|---|---|
| `mm/vmscan.c` | +18/−0 | MGLRU 内核级硬锁（拒绝清除 `LRU_GEN_CORE`） |
| `mm/migrate.c` | 0（已与 6.6.162 一致） | 原补丁 16 已被 6.6.157 原生包含 |
| `net/sched/sch_fq.c` | 0（已与 6.6.162 一致） | 原补丁 15 已被 6.6.160 原生包含 |
| `net/ipv4/tcp_bbr3_compat.h` | +363/−0（相对合并前 +1/−1） | BBRv3 兼容头；适配 6.6.162 三参数 `__tcp_send_ack(sk, rcv_nxt, 0)` |
| `drivers/ufs/core/ufs-mcq.c` | +40/−0（合并冲突解齐） | 保留 MTK UFS debug 逻辑并采用 6.6.162 上游 `ufshcd_mcq_compl_cqe()`，将 debug `tag` 收入 `#if IS_ENABLED(CONFIG_MTK_UFS_DEBUG)` |

**无任何意外改动。** 这是判断是否误改的重要基线。

## 9. 待办

- [x] 8 个补丁实机验证（2026-11-08 两批均开机成功）
- [x] 分成独立提交（保留上游 commit 溯源）
- [x] 补齐中文/英文 README 的 backport 清单与 6.6.162 / SuSFS v2.4.0 / BakaSU `57b2db60` 信息
- [x] 合并 AOSP `android15-6.6-lts`（6.6.162）、升级 SuSFS v2.4.0、同步 BakaSU `57b2db60` 并完成本地干净编译 + 魔数 + `--use-stg` 校验 + 刷新 `docs/abi-baseline.json`
- [ ] 实机刷入 `6.6.162` + SuSFS v2.4.0 + BakaSU `57b2db60` 验证开机、管理器识别、SuSFS 隐藏与日常稳定性
- [ ] 将当前工作区变更（SUSFS v2.4.0 + BakaSU `57b2db60` + `tcp_bbr3_compat.h` + CI 适配 + 基线与文档）提交并推送至 `origin/bsp-rodin-v-oss-bp`，恢复远端每日同步工作流
- [ ] 长期观察：待机电流、唤醒响应、Root/模块/相机/充电/指纹
- [ ] 从设备拉取厂商 `.ko`，跑一次完整 CRC 基线，建立出厂 ABI 指纹

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
| 直接整体 merge kernel.org stable / 升级 6.18 | 会丢失 `ANDROID:` 补丁与 `vendor_hooks` 或跨 KMI 世代导致闭源模块无法加载（LTS 升级必须走 AOSP `android15-6.6-lts`） |
