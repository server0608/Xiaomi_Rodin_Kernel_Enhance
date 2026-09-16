> 📚 本篇收录三篇指南（可用 TOC 快速跳转）：
> - [① 生成 .config 的经验指南（编译：defconfig + gki_defconfig / clang22）](#guide-config)
> - [② ReSukiSU-SUSFS 落地内核树指南：头文件重建与版本号计算](#guide-susfs)
> - [③ 使用 GitHub Actions 工作流编译内核（免本地环境）](#guide-ci)

<a name="guide-config"></a>

# 生成 .config 的经验指南（Rodin / Xiaomi_Rodin_Kernel_Enhance）

本指南总结在用 `.config` 并基于 clang22 全量编内核时踩过的坑与解法，供以后复用，避免重复踩坑。

适用内核树：`~/rodin-build/kernel-rodin-merge`（Xiaomi Rodin 6.6.x 分支 `bsp-rodin-kernel-oss-bp`）
编译器：Android 预编译 clang22：`$HOME/rodin-build/prebuilts/clang/host/linux-x86/clang-r596125/bin`

### 只能用 gki_defconfig 生成用于编译的 .config ，而不是 defconfig + gki_defconfig 或者其他的组合，否则会生成错误配置！

## 编译命令模板

```bash
export PATH="$HOME/rodin-build/prebuilts/clang/host/linux-x86/clang-r596125/bin:$PATH"
cd ~/rodin-build/kernel-rodin-merge
make ARCH=arm64 LLVM=1 -j8 Image Image.lz4
```

- 产物：`arch/arm64/boot/Image`（未压缩）、`arch/arm64/boot/Image.lz4`（LZ4 legacy 压缩）。
- 验证 lz4 legacy：`xxd arch/arm64/boot/Image.lz4 | head -1` 魔数应为 `0221 4c18`（`0x184C2102`），即 LZ4 Legacy，**不是** `0422 4d18`（标准帧格式）。
- 版本号在 `include/config/kernel.release`。


> 最后更新：2026-09-10

---

<a name="guide-susfs"></a>

# ReSukiSU-SUSFS 落地内核树指南：头文件重建与版本号计算

> 适用场景：把最新 `resukisu-susfs`（ReSukiSU Fork）的 kernel 模块源码「完整落地」到内核树
> `kernel-rodin-merge` 的 `drivers/kernelsu`，并在落地后用 `fix_kbuild.py` 固定正确的版本号。
>
> 本文档基于一次完整落地实践总结，包含两个易踩坑的环节：
> 1. **`uapi/` 头文件重建**（落地后编译必现，缺了会找不到头文件）
> 2. **版本号计算**（依赖 `fix_kbuild.py` 固化版本信息）

---

## 0. 路径约定

以下路径可按照实际环境替换。本文使用 WSL 中的路径：

| 含义 | 路径 |
|------|------|
| 源仓库（ReSukiSU） | `~/rodin-build/resukisu-susfs` |
| 内核树（目标落地位置） | `~/rodin-build/kernel-rodin-merge` |
| 源模块源码目录 | `<源根>/kernel` |
| 落地目标目录 | `<内核根>/drivers/kernelsu` |
| 版本修正脚本（Windows 侧） | `fix_kbuild.py` |

> Windows 与 WSL 路径映射：`\\wsl.localhost\<发行版>` 对应 `/`，例如
> `\\wsl.localhost\Ubuntu\home\<用户名>\rodin-build\...` == `/home/<用户名>/rodin-build/...`。

---

## 1. 完整落地源码到内核树

### 1.1 清空并重新拷贝

落地前先清理旧目录，再用 `rsync --delete` 让目标严格等于源目录：

```bash
cd <内核根>/drivers
rm -rf kernelsu                         # 清理旧版本，避免残留旧文件
rsync -rv <源仓库>/kernel/ ./kernelsu/  # 完整同步（保留符号链接与权限）
```

> 要点：`rsync` 配合 `--delete`（或 `-rv` 的删除语义）时，目标会删除源中不存在的文件，
> 所以源里被删掉的文件会在目标里被同步删掉——这正是第 2 节 `uapi/` 缺失问题的来源。

### 1.2 同步其它内核侧 SUSFS 文件

落地不只是拷贝 `drivers/kernelsu`，SUSFS 内核文件也要与源保持一致（落地完成后验证）：

```bash
diff <源根>/susfs4ksu/kernel_patches/include/linux/susfs.h  <内核根>/include/linux/susfs.h
diff <源根>/susfs4ksu/kernel_patches/fs/susfs.c              <内核根>/fs/susfs.c
# susfs_def.h 同理：来自 susfs4ksu/kernel_patches/include/linux/susfs_def.h
```

### 1.3 内核侧补丁（50/55/56）状态

- 内核侧补丁（如 `50_add_susfs_in_ath-6.1.patch`、`55_selinux_hook_hide...`、
  `56_selinuxfs_hide...`）来自 `susfs4ksu/kernel_patches/`。
- 若这些补丁**已打在树里**，再落地时不需要重复 `git apply`（会因已应用而失败）。
- 可用 `git apply --check` 判断；失败通常意味着已应用。

> 注意：`susfs4ksu/kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch` 是给**标准**
> KernelSU 用的。resukisu-susfs 的 `kernel/` 本身就内置 SUSFS（Kconfig 有 20 个
> `KSU_SUSFS` 项），因此**不要**对这个落地源再应用该补丁。

---

## 2. 头文件重建（关键坑）

### 2.1 问题现象

落地并 `rsync --delete` 后，会有如下报错表象：

```bash
git status --short               # 出现 D drivers/kernelsu/uapi/...
grep -rn 'uapi/' drivers/kernelsu  # 仍有多个源文件引用 "uapi/xxx.h"
```

即：落地后源文件仍 `#include "uapi/app_profile.h"` 等，但 `drivers/kernelsu/uapi/`
目录没了，编译会报找不到头文件。

### 2.2 根因

源仓库里，`kernel/`（模块源码）自身**并没有 `uapi/` 目录**，头文件在**仓库根目录的
`uapi/`**：

```text
resuki-susfs/
├── kernel/                  # 落地为 drivers/kernelsu
│   └── include/
│       └── uapi -> ../../uapi   # 软链接：指向仓库根目录 uapi/
└── uapi/                    # 真正头文件在这里
    ├── app_profile.h
    ├── feature.h
    ├── ksu.h
    ├── selinux.h
    ├── sulog.h
    └── supercall.h
```

源码 `kernel/include/uapi -> ../../uapi` 是相对软链接，在源仓库里指向仓库根的
`uapi/`；但 `kernel/` 被复制进内核树成 `drivers/kernelsu` 后，它的解析路径变成
`drivers/uapi`（**不存在**），即相对链接失效。

而内核侧 Kbuild 的包含路径是：

```makefile
ccflags-y += -I$(srctree)/$(src) -I$(srctree)/$(src)/include
```

也就是 `-Idrivers/kernelsu`，所以 `#include "uapi/xxx.h"` 实际解析到
`drivers/kernelsu/uapi/xxx.h`——需要一个**真实的 `drivers/kernelsu/uapi/` 目录**。

### 2.3 修复：重建真实 uapi/ 目录

把仓库根目录的 `uapi/*.h` 拷进内核树，建一个真实目录（不用软链接）：

```bash
SRC=<源根>/uapi
DST=<内核根>/drivers/kernelsu/uapi
mkdir -p "$DST"
cp "$SRC"/*.h "$DST/"
```

落地后应包含 6 个 `.h`：

```bash
ls <内核根>/drivers/kernelsu/uapi/
# app_profile.h  feature.h  ksu.h  selinux.h  sulog.h  supercall.h
```

### 2.4 include/uapi 软链接

`drivers/kernelsu/include/uapi -> ../../uapi` 在内核树里会解析到 `drivers/uapi`
（不存在），是**无效软链接**，对编译无作用：

- 保留即可（与 git 已提交状态保持一致）；
- 真实头文件由 `drivers/kernelsu/uapi/` 真实目录提供。

---

## 3. 版本号计算与修正

### 3.1 版本号来源（从源仓库 git 读取）

版本号公式（内核 Kbuild 原始定义）：

```text
KSU_VERSION = 30000 + KSU_LOCAL_VERSION + 700
```

需要 4 个字段，全部来自**源仓库**（非内核树）：

```bash
cd <源根>   # 例如 ~/rodin-build/resukisu-susfs

KSU_LOCAL_VERSION=$(git rev-list --count HEAD)                        # 例 4427
KSU_TAG_NAME=$(git describe --abbrev=0 --tags 2>/dev/null || echo v4.1.0)  # 例 v4.2.0-rc1
KSU_COMMIT_SHA=$(git rev-parse --short=8 HEAD)                        # 例 23a40c0f
KSU_BRANCH_NAME=$(git branch --show-current)                          # 例 main-susfs

KSU_VERSION=$((30000 + KSU_LOCAL_VERSION + 700))                      # 例 35127
```

### 3.2 为什么不能用内核树自己的 git（fix_kbuild.py 存在的意义）

Kbuild 默认行为是从 `$(KSU_SRC)` 查 git 拿这些值。但落地后：

- `drivers/kernelsu/` 本身已是内核树 git 仓库的一部分；
- 若让内核树去查询，读到的是**内核树的 commit 数/sha/脏状态**，而非 ReKSU 的。

因此 `fix_kbuild.py` 把 Kbuild 的 git 查询分支替换为：`LOCAL_GIT_EXISTS=1` 时查
git（外部构建），否则**直接写入固化的版本号**。

### 3.3 fix_kbuild.py 用法

脚本是**幂等**的文本替换器，落地完成后运行：

```bash
python3 fix_kbuild.py
# 输出 "ALREADY PATCHED"（已打过）或 "PATCHED OK"（刚打好）
# 若 old 块未找到会 abort（通常表示 new 已在）
```

它会：
1. 用 `old` 块匹配内核 Kbuild 中原始的 git 查询段；
2. 替换为 `new` 块（固化版本号 + `ifeq/else/endif` 分支）；
3. 我已修复判断顺序，优先检测 `new` → 输出 `ALREADY PATCHED`，避免误报 `ABORT`。

替换后 Kbuild 应含：

```makefile
ifeq ($(LOCAL_GIT_EXISTS),1)
$(shell cd $(KSU_SRC); ...)
KSU_LOCAL_VERSION := $(shell ...)
...
else
# Vendored as an in-tree copy of ReSukiSU main-susfs @ 23a40c0f. ...
KSU_LOCAL_VERSION := 4427
KSU_TAG_NAME    := v4.2.0-rc1
KSU_COMMIT_SHA  := 23a40c0f
KSU_BRANCH_NAME := main-susfs
endif
KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)
```

### 3.4 验证版本

```bash
grep -n 'KSU_VERSION\|KSU_LOCAL_VERSION\|KSU_TAG_NAME\|KSU_COMMIT_SHA\|KSU_BRANCH_NAME' \
  <内核根>/drivers/kernelsu/Kbuild
```

期望：`KSU_LOCAL_VERSION := 4427`、`KSU_COMMIT_SHA := 23a40c0f`、
`KSU_VERSION := ...30000 + 4427 + 700`（`35127`）。

---

## 4. 落地后自检清单

| 检查项 | 命令 |
|--------|------|
| 无未跟踪产物 | `git status --short \| grep '^??'` 为空 |
| 无意外删除 | `git status --short \| grep '^ D'` 为空 |
| hook 目录完整 | `ls drivers/kernelsu/hook/`（arm32/arm64/x86_64 + 钩子）|
| ksu.h 含版本宏 | `grep KERNEL_SU_VERSION drivers/kernelsu/include/ksu.h` |
| uapi 头齐备 | `ls drivers/kernelsu/uapi/`（6 个 .h） |
| 版本固化 | 见 3.4 |

通过后 `git add -A && git commit`。

---

## 5. 本次最终值（供参考）

| 项 | 值 |
|----|----|
| 源分支 | `main-susfs` |
| 源 commit | `23a40c0f` |
| tag | `v4.2.0-rc1` |
| KSU_LOCAL_VERSION | `4427` |
| KSU_VERSION（固定值） | `35127` |
| 落地提交 | `a5724993c054` |

> 最后更新：2026-09-13

---

<a name="guide-ci"></a>

# ③ 使用 GitHub Actions 工作流编译内核（免本地环境）

**你可以使用工作流编译内核！** 不需要本地 WSL、工具链和几十 GB 源码：仓库自带的
`.github/workflows/build-kernel.yml` 在云端完成 clang-r596125 全量编译、lz4 legacy
打包和 ReSukiSU 管理器配对下载，产物下载即用。

## 触发方式

- 手动：仓库 **Actions** → 左侧选 **build-kernel** → **Run workflow** → 分支保持
  `bsp-rodin-v-oss-bp` → 点击运行（需要重建已发布过的版本时勾选 `force`）；
- 命令行：`gh workflow run build-kernel.yml -R <owner>/Xiaomi_Rodin_Kernel_Enhance --ref bsp-rodin-v-oss-bp`；
- 自动（每日）：`sync-android15-6.6-lts`（18:30 UTC）与 `sync-resukisu`（18:50 UTC）
  成功后经 `workflow_run` 链式触发；另有 19:15 UTC（次日 03:15 UTC+8）的 `schedule`
  兜底一次，防止两个同步工作流失败时当天没有构建。

三者都会先跑一个轻量 `gate`（约 1 分钟）：读取**最新 Release 正文里的
`rodin-build-sha` 标记**，若分支 tip 已经构建并发布过就跳过编译，因此不会因为
多次触发而在同一天重复出包。

## 自动化闭环（每日同步 → 构建 → 发布）

```text
18:30 UTC  sync-android15-6.6-lts  ──┐
18:50 UTC  sync-resukisu           ──┤ 成功后 workflow_run 链式触发
                                   └──────────────┐
                                                   ▼
                                          build-kernel (gate → build)
                                                   ▼
                                    GitHub Release v<内核版本>-<UTC时间戳>
```

Release 资产：`Rodin-<版本>-AnyKernel3.zip`（可刷包）+ 两个 arm64-v8a 管理器 APK。

## 它在云端做什么

1. 下载 AOSP 预编译 clang-r596125（googlesource `mirror-goog-main-llvm-toolchain-source`
   分支 tarball，失败自动回退固定 commit 直链 / sparse clone）；
2. 按指南①的结论生成配置：`make ARCH=arm64 LLVM=1 gki_defconfig`（只用 gki_defconfig），
   然后 `make ARCH=arm64 LLVM=1 -j"$(nproc)" Image Image.lz4`；
3. 校验 `Image.lz4` 魔数为 `02214c18`（LZ4 legacy）；若不是则自动用 `lz4 -l` 重压并复检；
4. 组装 AnyKernel3（WildKernels gki-2.0）：内核 blob 命名为 `Image`（设备只认这个名字），
   内容为 lz4 legacy 压缩的内核，并写入版本号到 kernel.string；
5. 从 ReSukiSU 上游 main 的 Build Manager CI 中，取与内核树 `drivers/kernelsu/Kbuild`
   固定的 `KSU_COMMIT_SHA` **相同 commit** 的构建产物（管理器与内核模块版本严格一致），
   过滤后只保留 arm64-v8a 的 release 与 spoofed 两个 APK。

## 产物（Run 页 artifact + 自动发布的 Release）

| 产物 | 内容与用法 |
|---|---|
| `Rodin-<版本>-AnyKernel3`（artifact） | 可刷包本体。下载得到的 zip 就是 AK3 包（根目录 `anykernel.sh` / `Image` / `META-INF/`），TWRP/KernelSU 直接选中刷入，**无需先解包** |
| `rodin-<版本>-manager`（artifact） | ReSukiSU 管理器 release 变体（arm64-v8a 单 APK） |
| `rodin-<版本>-manager-spoofed`（artifact） | ReSukiSU 管理器 spoofed 变体（arm64-v8a 单 APK） |
| `Rodin-<版本>-AnyKernel3.zip` + 两个 APK（Release） | 同一个构建的正式发布：tag 形如 `v6.6.30-…-20260913-1915`，tag 指向被编译的那个 commit |

## 注意

- 全量 ThinLTO 编译约 35–45 分钟（4 核 runner），任一步失败即中止，日志可直接定位到具体步骤；
- 去重：`gate` 通过 Release 正文的 `rodin-build-sha` 标记识别「这个 commit 已经出过包」，
  同一天多次触发只会产生一个 Release；需要重刷时手动触发并勾选 `force`；
- 管理器版本一致性：按 `KSU_COMMIT_SHA` 精确匹配上游 CI run；若对应产物已过期（GitHub
  默认保留 90 天），自动回退到上游最新成功构建并在日志中 `::warning` 提示；
- 权限：本工作流需要 `contents: write` 才能创建 tag 与 Release（已写在 workflow 里）。

> 最后更新：2026-09-13（新增：每日同步 → 自动构建 → 发布 Release 的链式闭环）
