# AGENTS.md — 项目上下文入口

> 本文件供 AI 助手自动加载。**动手前必读**，尤其是「硬约束」一节。
> 细节见 [`docs/PROJECT-STATE.md`](docs/PROJECT-STATE.md)（现状台账）与
> [`docs/PATCH-AUDIT.md`](docs/PATCH-AUDIT.md)（补丁审计记录）。

## 1. 项目身份

| 项 | 值 |
|---|---|
| 设备 | 小米 Redmi Turbo 4 / POCO X7 Pro，代号 **rodin** |
| SoC | MediaTek **MT6897** Dimensity 8400 Ultra，8× Cortex-A725（1+3+4） |
| 系统 | HyperOS 3（Android 16），**GKI** 架构，GKI 世代 `android15-6.6` |
| 内核 | Linux **6.6.144**，arm64，`-mcpu=cortex-a725` |
| 分支 | `bsp-rodin-v-oss-bp`（主构建分支） |
| 基线 | AOSP `android15-6.6-lts`（ACK） |

**GKI 关键事实**：触摸、充电、指纹、摄像头、基带等驱动是**闭源预编译 `.ko`**，
位于 `vendor_dlkm` / `vendor_boot`，我们无法重编。我们只替换 `boot` 分区的 `Image`。

## 2. 硬约束（违反即事故）

1. **禁止改动结构体布局与导出符号原型。**
   `task_struct`、`sched_avg`、`cpufreq_policy`、`module` 等被导出符号引用的结构体，
   任何字段增删改都会改变符号 CRC，导致闭源模块 ABI 错位。
   详见 [`docs/KMI-ABI-CHECK.md`](docs/KMI-ABI-CHECK.md)。
   > 例：`6d71a9c61604`（EEVDF 放置重构）因需给 `struct sched_entity` 新增
   > `rel_deadline` 字段而被**拒绝**，即使性能收益可观。

2. **启用任何 Kconfig 选项前，必须确认它不改变结构体布局。**
   配置项可以偷偷给冻结 ABI 的结构体加字段。
   `CONFIG_READ_ONLY_THP_FOR_FS=y` 就会给 `struct address_space` 加
   `atomic_t nr_thps`（240 → 244 字节），直接导致实机卡在 logo 不动。
   每次改配置或改代码后，**刷机前必须运行**：
   ```bash
   scripts/abi-guard.py            # 对比已验证构建的类型基线
   ```
   详见 [`docs/KMI-ABI-CHECK.md`](docs/KMI-ABI-CHECK.md)。

3. **禁止整体 merge kernel.org stable。**
   只做**精选 cherry-pick**。AOSP ACK 分支携带大量 `ANDROID:` 补丁与
   `vendor_hooks`（`kernel/sched/vendor_hooks.c` 单文件就有 120 个导出点），
   整体合并极易静默丢失，导致能开机但调频/调度失效。

4. **禁止恢复 `preinit/runner.elf`。**
   必须在编译时保持 `-DKSU_NO_PREINIT`。BakaSU 的 preinit 会劫持 PID 1，
   在 HyperOS 上直接 bootloop。该宏定义在：
   - `drivers/kernelsu/tools/code_generation/code_generation.mk`
   - `drivers/kernelsu/tools/code_generation/preinit_runner/preinit_runner.mk`
   - `.github/workflows/sync-resukisu.yml`（同步后自动重新追加，勿删）

5. **BBRv3 + FQ 硬锁不可移除。**
   `net/ipv4/sysctl_net_ipv4.c` 与 `net/core/sysctl_net_core.c` 中的
   sysctl 白名单用于拦截 Android userspace（`init.rc`）覆写，是刻意设计。

6. **单 patch 流程，顺序不可跳步：**
   ```
   上游 diff 审计 → 最小化改动 → 本地构建 → ABI 校验 → 魔数校验 → 实机 A/B → 提交推送
   ```
   **未经实机验证不得提交，不得宣称性能提升。**

   补丁来源只接受**已合入 mainline 或 stable** 的提交。未合入的 RFC / 提案
   一律暂缓——变砖事故后已确立此策略。

7. **不得虚构收益。**
   没有 A/B 数据就不写"提升 X%"。README 措辞保持"反向移植上游修复"。

## 3. 构建与校验

```bash
./build-local.sh          # 增量约 1.5 分钟
```

编译后**必须**核对两个魔数，否则刷入即变砖：

| 目标 | 期望字节 | 检查命令 |
|---|---|---|
| `arch/arm64/boot/Image` @0x38 | `41 52 4d 64`（`ARMd`） | `od -An -tx1 -j56 -N4 arch/arm64/boot/Image` |
| `arch/arm64/boot/Image.lz4` | `02 21 4c 18`（LZ4 legacy） | `od -An -tx1 -N4 arch/arm64/boot/Image.lz4` |

工具链：`/home/server0608/toolchains/clang-r596125`（Google Clang 22）。

## 4. 常用审计命令

```bash
# 我们相对 AOSP 基线的全部改动
git diff --stat aosp/android15-6.6-lts -- kernel/sched/

# 是否落后 AOSP（应为空）
git log --oneline aosp/android15-6.6-lts --not HEAD -- kernel/sched/

# 拉取 LTS 用于精选审计
git fetch --no-tags stable refs/tags/v6.6.162:refs/tags/v6.6.162
git log --oneline v6.6.144..v6.6.162 -- kernel/sched/

# 上游补丁原文
curl -fsSL "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/patch/?id=<sha>"
```

## 5. 环境注意事项

- **`web_search` 不要指定 `provider` 参数。** 传了会强制校验对应 API key 而失败；
  只传 `queries: [...]` 即走默认托管通道。
- 拉取 GitHub 受阻时用 `https://gh-proxy.com/` 前缀。
- `drivers/kernelsu/compat/syscall_no.h` 与
  `drivers/kernelsu/tools/code_generation/syscall_no/syscall_no`
  是构建产物，已在 `.gitignore` 中忽略。

## 6. 当前状态速查

- 内核 6.6.144，与 AOSP `android15-6.6-lts` **完全同步**（零落后）。
- 已合入 backport **17 个**：9 个已提交，8 个待实机验证
  （调度 4 + 内存 2 + 网络 1 + 配置 1）。
- 待验证刷机包：`out/AnyKernel3-Rodin-6.6.144-...-840883-*.zip`
- 配套管理器：BakaSU 版本号 **35257**，内核模块 commit `516d3e87`。

完整台账见 [`docs/PROJECT-STATE.md`](docs/PROJECT-STATE.md)。

## 7. 文档维护约定

上下文会被压缩，**文档是唯一可靠记忆**。因此：

1. **状态变了就改 `docs/PROJECT-STATE.md`**——版本、HEAD、补丁清单、待办。
   不要只口头告知，务必写回文件。
2. **审计完一个补丁就追加 `docs/PATCH-AUDIT.md`**——即使是拒绝的也要写，
   否则未来会重复调研同一个补丁。
3. **本文件（`AGENTS.md`）只放硬约束与入口**，保持精简，不要堆细节。
4. **写入前先验证事实**。不确定的数字（版本、SHA、配置项）先查再写，
   宁可写“待确认”也不要写错。
5. 提交时把文档一起提交，保证仓库自描述。
