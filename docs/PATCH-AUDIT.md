# 补丁审计记录

> 记录每个候选补丁的**审计结论与理由**，防止后续重复调研或误推翻决定。
> 新增补丁请追加，不要删除历史条目。现状见 [`PROJECT-STATE.md`](PROJECT-STATE.md)。

## 审计方法论

每个候选补丁必须回答四个问题：

1. **上游原文**是什么？逐行比对，不看二手描述。
   ```bash
   curl -fsSL "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/patch/?id=<sha>"
   ```
2. **是否触碰 ABI？** 有没有改结构体布局、导出符号原型、删除导出？
   有 → 直接拒绝，无论收益多大。
3. **依赖链有多长？** 是否需要先移植其它补丁或基础设施？
   依赖长 → 拒绝，维护成本不可控。
4. **在本平台上是否真的生效？** 例如 SMT 相关补丁在 arm64 上无效，
   32 位溢出修复在 arm64 上无效。

只有四条全部通过，才进入"最小化改动 → 构建 → 魔数 → 实机 A/B"。

---

## 已合入

### 补丁 1 — `29922fdfc2a4` Fix cpu_util runnable_avg arithmetic

- **问题**：`cpu_util()` 在 `boost` 路径上的 runnable_avg 算术有误，
  导致 CPU 利用率估算偏高/偏低，影响调频与选核。
- **改动面**：`cpu_util()` 函数体内算术。
- **ABI**：无。
- **结论**：合入，本地 `2659273a6b5d`。

### 补丁 2 — `f2d650618bc7` Allow decaying util_est when util_avg > CPU capa

- **问题**：当 `util_avg` 超过 CPU 容量时，`util_est` 无法衰减，
  历史峰值被长期保留，导致长期运行在过高频点。
- **改动面**：`util_est_update()`。
- **ABI**：无。
- **结论**：合入，本地 `5fe9e53df79a`。**与功耗改善直接相关。**

### 补丁 3 — `4f166adb5cb0` Fix overflow in update_tg_cfs_runnable()

- **问题**：`update_tg_cfs_runnable()` 存在溢出，任务组 runnable 统计失真。
- **改动面**：单函数。
- **ABI**：无。
- **结论**：合入，本地 `fc4e76ae3b8b`。

### 补丁 4 — `72bffbf57c52` Fix initial util_avg calculation

- **问题**：新建实体初始 `util_avg` 计算错误，新任务被错误地判定为重负载。
- **改动面**：`init_entity_runnable_average()`、`post_init_entity_util_avg()`。
- **ABI**：无。
- **结论**：合入，本地 `86c172962385`。

### 补丁 5 — `cdd9e37ed46a` Don't trigger active lb if src_rq->curr is not on_rq

- **问题**：`src_rq->curr` 不在 runqueue 上时仍触发 active load balance，
  造成无谓的迁移开销。
- **改动面**：`load_balance()`。
- **ABI**：无。
- **结论**：合入，本地 `83e09dcf6bc6`。

### 补丁 6 — `50b101f6e586` Check CPU capacity before comparing group types

- **问题**：`update_sd_pick_busiest()` 先比较 `group_type` 再看容量，
  导致容量不足的组被误选为 busiest。
- **改动面**：把容量检查**前移**到 `group_type` 比较之前。
- **ABI**：无。
- **结论**：合入，本地 `34849521a42a`。已在实机验证。

### 补丁 7 — `58eeb2d79b54` Don't double balance_interval for migrate_misfit

- **问题**：`migrate_misfit` 场景下 `balance_interval` 被重复加倍，
  负载均衡响应变慢。
- **改动面**：`load_balance()` 内间隔计算。
- **ABI**：无。
- **结论**：合入，本地 `3ae9af4f0507`。**用户实测功耗下降。**

### 补丁 8 — `7f1a7229718d` Do strict inequality check for busiest misfit group

- **问题**：`group_misfit_task_load` 比较用 `<` 而非 `<=`，
  相等时误判，导致 misfit 组未被正确选中。
- **改动面**：`update_sg_lb_stats()` 一处比较。
- **ABI**：无。
- **结论**：合入，本地 `b1b38d3f725e`。

### 补丁 9 — `d3d663faa1d4` Filter false overloaded_group case for EAS

- **问题**：EAS 下，某 CPU 因 uclamp 限制容量而满载时，`group_overloaded`
  优先级高于 `group_misfit`，导致该组被误选为 busiest，
  阻止了真正的 misfit 迁移。
- **改动面**：`group_is_overloaded()`。
- **ABI**：无。
- **结论**：合入，本地 `f181620517e1`。已发布。

### 补丁 10 — `79443a7e9da3` Explicitly synchronize limits_changed flag

- **问题**：`sugov_should_update_freq()` 中清 `limits_changed` 与
  `cpufreq_driver_resolve_freq()` 读取策略上限之间缺少内存序约束。
  理论上可被重排，导致新的调频上限**长时间不生效**——CPU 卡在低频。
- **改动面**：`READ_ONCE`/`WRITE_ONCE` + `smp_mb()`/`smp_wmb()`。
- **ABI**：无。
- **结论**：合入。与上游 diff 完全一致（+24/−4）。
- **待办**：实机验证重负载下频率跟手性。

### 补丁 11 — `82d6e01a0699` Only update stats for allowed CPUs

- **问题**：`update_sg_wakeup_stats()` 用 `for_each_cpu()` 遍历整个调度组，
  把**亲和性不允许的 CPU** 的 idle 数也算进去。线程频繁 fork 时，
  调度器会选中一个实际拥挤的组，同时真正空闲的组被浪费。
- **改动面**：`for_each_cpu` → `for_each_cpu_and(..., p->cpus_ptr)`，一行。
- **ABI**：无。
- **结论**：合入。Android 上 HAL/cpuset 大量使用亲和性，收益可期。

### 补丁 12 — `4423af84b297` optimize PLACE_LAG when se->vlag is zero

- **问题**：`place_entity()` 中 `vlag == 0` 时，后续 `div_s64` 结果必然为 0，
  属纯浪费。
- **改动面**：条件加 `&& se->vlag`。
- **ABI**：无。
- **结论**：合入。唤醒/入队热路径省一次 64 位除法，语义等价。
- **注意**：上游配套的 `c70fc32f4443` 是修复 `6d71a9c61604` 引入的 WARN，
  我们不移植 `6d71a9c61604`，因此**不需要**它。

### 补丁 13 — `926475806606` Update overutilized detection

- **问题**：`cpu_overutilized()` 传入 `uclamp_rq_get(UCLAMP_MIN)`，但自
  `e5ed0550c04c` 后 `util_fits_cpu()` 在 `uclamp_min > capacity_orig_thermal`
  时返回 `-1`，而 `!(-1) == 0` 本就等同于"未过载"。
- **改动面**：删除一次 `uclamp_rq_get()` 调用，`uclamp_min` 改传 `0`。
- **ABI**：无。
- **等价性**：逐分支验证，返回 `-1` 与返回 `fits==1` 经 `!` 后均为 false，**行为完全等价**。
- **结论**：合入，纯热路径微优化（每次 overutilized 检查省一次函数调用）。

### 补丁 15 — `709f34f7c28d` net/sched: fq: add overflow bounds to quantum

- **问题**：`fq_init()` 用 `2 * psched_mtu()` 且无溢出检查。超大 MTU（如 dummy 设备）
  使乘法回绕为 0，`q->quantum == 0`，`fq_dequeue()` 在 qdisc 锁下**死循环**。
- **改动面**：`mtu = clamp_t(u32, psched_mtu(...), 1, 1 << 20)`，
  再 `min_t(u32, N * mtu, 1 << 20)`。
- **ABI**：无。
- **相关性**：本项目硬锁 FQ，且用户态可配置 MTU，故必须修。
- **结论**：合入（本地 `fd63409b669f`）。

### 补丁 16 — `efe8f86c0916` mm/migrate: report RCU-tasks quiescent states

- **问题**：`migrate_pages_batch()` 批量 unmap 期间 `cond_resched()` 在
  PREEMPTION 内核上是 no-op，而被动抢占不算 Tasks-RCU 静默态。
  长批次（如 kcompactd 迁移大量 folio）会成为 RCU-tasks holdout，
  导致 RCU 优雅期停滞数分钟，表现为整机卡死。
- **改动面**：一处 `cond_resched()` → `cond_resched_tasks_rcu_qs()`。
- **ABI**：无。
- **结论**：合入（本地 `4757542649af`）。内存压力下压缩/迁移场景直接受益。


## 已拒绝

### `CONFIG_READ_ONLY_THP_FOR_FS=y` — **导致实机变砖，已回退**

**事故记录（2026-11-08）**

这个选项看起来只是打开一个 THP 特性，实际上它会改变**冻结 ABI 结构体**的布局：

```c
struct address_space {
	...
	atomic_t		i_mmap_writable;
#ifdef CONFIG_READ_ONLY_THP_FOR_FS
	atomic_t		nr_thps;      /* ← 多出来的字段 */
#endif
	...
} __attribute__((aligned(sizeof(long)))) __randomize_layout;
```

`android/abi_gki_aarch64.stg` 里明确冻结了该结构体：

```
name: "address_space"
definition {
  bytesize: 240        ← 冻结大小
  16 member_id 条目
}
```

启用后变成 244/248 字节。闭源厂商模块按 240 字节编译，
所有字段偏移错位 → 开机过程踩内存 → **卡在品牌 logo 不动**。

**为什么内核没拦住**：`CONFIG_MODULE_FORCE_LOAD=y`，`try_to_force_load()`
无条件返回成功，CRC 不匹配只打 taint 标记，模块照常加载。

**教训**：Kconfig 选项可以改变结构体布局。启用任何新配置前，
必须用 `scripts/abi-guard.py` 比对类型大小。

**结论**：永久拒绝。

### 补丁 14 — MGLRU `lru_gen_use_mm()` 条件写入（暂缓）

- 语义等价性已逐分支验证，无 ABI 影响。
- 但来源是 **2026-11-05 的 RFC，尚未进入 mainline**。
- 在变砖事故后采取保守策略：只接受已合入 mainline/stable 的补丁。
- **结论**：暂缓，待上游合入后再评估。

### `6d71a9c61604` Fix EEVDF entity placement bug causing scheduling lag

- **收益**：修复 EEVDF 放置 bug，社区报告对 6.6 的性能回退有明显改善。
- **拒绝理由**：需要给 `struct sched_entity` 新增 `rel_deadline` 字段，
  并删除 `reweight_eevdf()` 改为 `place_entity()` 重入。
  **结构体布局改变 → KMI 破坏 → 闭源模块 ABI 错位。**
- **代价评估**：收益远小于"随机 panic"的风险。**永久拒绝**，除非换 KMI 世代。

### `c70fc32f4443` Adhere to place_entity() constraints

- **拒绝理由**：纯粹是 `6d71a9c61604` 的配套修复，母补丁不移植则无意义。

### `3167b620815c` Reject misfit pulls onto busy SMT siblings

- **拒绝理由**：依赖 `sched_smt_active()`。arm64（含 MT6897）无 SMT，
  该分支恒不执行，**零收益**。

### `aa436b021e50` Fix rate limit overflow

- **拒绝理由**：`rate_limit_us * NSEC_PER_USEC` 在 32 位 `unsigned long` 上溢出。
  arm64 的 `unsigned long` 为 64 位，**不会溢出**，修复无效。
- **备注**：若将来移植到 32 位平台需重新评估。

---

## 待评估

暂无。后续候选在审计后追加。

---

## 调研过的无效方向

| 方向 | 结论 |
|---|---|
| 整体 merge kernel.org 6.6.162 | 6876 个提交，会丢失 `ANDROID:` 补丁、破坏 vendor_hooks，且 AOSP 未推进。**否决** |
| `sched/fair: Add L2 cache awareness`（SIS_CACHE） | 十余个补丁的系列，改动面大、回归风险高。暂缓 |
| `schedutil` 频率参考 25% margin | 我们的树已包含 `e37617c8e53a`，与主线一致，无需改动 |
| EEVDF `PLACE_LAG` / `RUN_TO_PARITY` 改为 sysctl | 涉及 `sched_feat` 与用户可见接口，收益不确定。暂缓 |
