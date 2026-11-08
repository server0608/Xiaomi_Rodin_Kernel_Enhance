# KMI / ABI 兼容性校验

GKI 架构下，小米内核有一部分驱动是**闭源的**，以预编译 `.ko` 形式存在于
`vendor_dlkm` / `vendor_boot` 分区，我们无法重新编译。这些模块编译时绑定了一份
固定的 ABI，内核加载时通过**符号 CRC** 校验。

本文说明为什么这会导致"能开机但随机重启"，以及如何在刷机前用脚本把风险量化。

## 1. 为什么版本号不是问题

`kernel/module/version.c`：

```c
/* First part is kernel version, which we ignore if module has crcs. */
int same_magic(const char *amagic, const char *bmagic, bool has_crcs)
{
	if (has_crcs) {
		amagic += strcspn(amagic, " ");
		bmagic += strcspn(bmagic, " ");
	}
	return strcmp(amagic, bmagic) == 0;
}
```

本内核 `CONFIG_MODVERSIONS=y`，因此 `has_crcs` 为真，**vermagic 里的版本号段被跳过**，
只比较 `SMP preempt mod_unload modversions aarch64`。

结论：内核从 `6.6.144` 改成 `6.6.162`、或 release 串变成
`6.6.144-403Forbidden-...-dirty`，都**不会**因此被拒绝加载模块。

## 2. 真正的风险：符号 CRC 不匹配

CRC 由**符号签名 + 它涉及的结构体布局**算出。给 `task_struct` 加一个字段，
`activate_task` 的 CRC 立刻改变。

`vmlinux.symvers` 里记录了本内核全部导出符号的 CRC：

```
0xfaa77fa1	__put_task_struct
0x86aabb46	activate_task
0x5d6fbd94	cpufreq_driver_resolve_freq
0x65266df1	module_layout
```

## 3. 最危险的地方：内核不会拦住你

`check_version()` 发现不匹配时：

```c
bad_version:
	pr_warn("%s: disagrees about version of symbol %s\n", info->name, symname);
	return try_to_force_load(mod, symname) == 0;
```

而 `try_to_force_load()` 在本内核的配置下：

```c
int try_to_force_load(struct module *mod, const char *reason)
{
#ifdef CONFIG_MODULE_FORCE_LOAD
	add_taint_module(mod, TAINT_FORCED_MODULE, LOCKDEP_NOW_UNRELIABLE);
	return 0;          /* 永远返回成功 */
#else
	return -ENOEXEC;
#endif
}
```

`CONFIG_MODULE_FORCE_LOAD=y`，所以 CRC 不匹配**不会阻止加载**，只会打一个 taint 标记。

后果：厂商模块带着旧的结构体布局，去读写新结构体 →
**静默内存踩踏 → 开机正常、用一段时间后随机 panic / 重启**。

这比"直接开不了机"更难排查。**正因为内核不会拦，必须在刷机前主动校验。**

## 4. 刷机前校验

### 4.1 从设备取出厂商模块

```bash
# 常见路径，按需全部拉取
adb pull /vendor/lib/modules            ./vendor-modules/vendor
adb pull /vendor_dlkm/lib/modules       ./vendor-modules/vendor_dlkm
```

### 4.2 运行校验

```bash
scripts/kmi-crc-check.py ./vendor-modules
```

正常输出：

```
kernel symbol table : vmlinux.symvers
exported symbols    : 16743
modules checked     : 214

summary: 214 ok, 0 failed, 0 skipped
All compared symbols match; these modules are safe to load.
```

发现 ABI 变动：

```
[FAIL] mtk_disp.ko: 41/43 symbols match
    CRC mismatch  activate_task
      module expects 0x580705a9
      kernel exports 0x86aabb46
```

`module_layout` 不匹配是最强信号——说明 `struct module` 本身变了，
通常意味着 ABI 已经不可挽回。

### 4.3 退出码

| 码 | 含义 |
|---|---|
| `0` | 全部符号匹配，可刷 |
| `1` | 存在 CRC 不匹配或符号缺失，**不要刷** |
| `2` | 用法或 I/O 错误 |

可直接接入 CI：

```bash
scripts/kmi-crc-check.py --json ./vendor-modules > kmi-report.json
```

## 4.4 结构体布局校验（Kconfig 也能改 ABI）

`kmi-crc-check.py` 比对的是**厂商模块**的期望 CRC，需要先从设备拉模块。
本地更快的防线是直接比对**结构体大小**：

```bash
scripts/abi-guard.py            # 对比已验证构建的类型基线
scripts/abi-guard.py --use-stg  # 对比 AOSP 冻结快照
scripts/abi-guard.py --write-baseline   # 记录当前构建为新基线
```

基线文件：`docs/abi-baseline.json`（由**实机验证通过**的构建生成）。

**真实案例**：`CONFIG_READ_ONLY_THP_FOR_FS=y` 看起来只是打开一个 THP 特性，
实际会给 `struct address_space` 加 `atomic_t nr_thps`：

```
name: "address_space"
definition {
  bytesize: 240        ← 冻结值
  16 member_id
}
```

启用后变 244/248 字节。厂商模块按 240 字节编译，字段偏移全部错位，
开机过程踩内存 → **卡在品牌 logo 不动**。

**结论：任何 Kconfig 改动后，刷机前必须跑一次 `abi-guard.py`。**

## 5. 安全改动的边界

| 操作 | 是否安全 |
|---|---|
| 改版本号 / release 字符串 | 安全，不参与校验 |
| 改函数内部实现 | 安全，CRC 不变 |
| 新增函数或静态函数 | 安全 |
| 改 `struct task_struct` / `sched_avg` / `cpufreq_policy` 等导出结构体布局 | **禁止** |
| 删除或重命名已导出符号 | **禁止** |
| 整体 merge 新 LTS 且冲突解错 | 高风险，必须跑本脚本 |

## 6. 注意

脚本只比对**内核镜像导出的符号**（`vmlinux.symvers`）。若某模块依赖另一个模块，
相关符号会显示为 "not exported by this kernel"，属正常情况，只要导出方模块也在设备上即可。
