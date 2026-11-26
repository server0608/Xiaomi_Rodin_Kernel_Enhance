> 📚 本篇收录三篇指南（可用 TOC 快速跳转）：
> - [① 生成 .config 与本地编译校验指南（只用 gki_defconfig / clang22）](#guide-config)
> - [② BakaSU（原 ReSukiSU）与 SuSFS v2.4.0 落地内核树指南：头文件重建、版本固化与接口校验](#guide-susfs)
> - [③ 使用 GitHub Actions 工作流编译内核（免本地环境）](#guide-ci)

<a name="guide-config"></a>

# 生成 .config 与本地编译校验指南（Rodin / Xiaomi_Rodin_Kernel_Enhance）

本指南总结在用 `.config` 并基于 clang22 全量编内核时踩过的坑与解法，供以后复用，避免重复踩坑。

适用内核树：`Xiaomi_Rodin_Kernel_Enhance`（Xiaomi Rodin 6.6.x 主构建分支 `bsp-rodin-v-oss-bp`）
编译器：Android 预编译 clang22（`clang-r596125`，本机路径 `/home/server0608/toolchains/clang-r596125/bin`）

### 只能用 gki_defconfig 生成用于编译的 .config ，而不是 defconfig + gki_defconfig 或者其他的组合，否则会生成错误配置！

## 本地一键构建脚本

仓库根目录已提供 [`build-local.sh`](build-local.sh)（自动完成 `gki_defconfig`、全核编译、LZ4 Legacy 魔数校验与 AnyKernel3 打包，输出至 `out/AnyKernel3-Rodin-*.zip`）：

```bash
./build-local.sh
```

> 提示：切换或更新 AOSP AutoFDO profile（`android/gki/aarch64/afdo/`）后，必须先执行 `make ARCH=arm64 LLVM=1 clean` 再重新编译，避免 ThinLTO `ProfileSummary` 不一致报错。

## 手动编译命令模板

```bash
export PATH="/home/server0608/toolchains/clang-r596125/bin:$PATH"
cd ~/Xiaomi_Rodin_Kernel_Enhance
make ARCH=arm64 LLVM=1 gki_defconfig
make ARCH=arm64 LLVM=1 -j"$(nproc)" Image Image.lz4
```

- 产物：`arch/arm64/boot/Image`（未压缩）、`arch/arm64/boot/Image.lz4`（LZ4 legacy 压缩）。
- 验证 ARM64 内核头魔数（@0x38）：`od -An -tx1 -j56 -N4 arch/arm64/boot/Image` 应为 `41 52 4d 64`（`ARMd`）。
- 验证 lz4 legacy：`od -An -tx1 -N4 arch/arm64/boot/Image.lz4` 应为 `02 21 4c 18`（`0x184C2102`），即 LZ4 Legacy，**不是** `04 22 4d 18`（标准帧格式）。
- 刷机前 ABI 校验：`scripts/abi-guard.py`（须退出码 0；合并新 AOSP 基线时另执行 `scripts/abi-guard.py --use-stg` 对照冻结 GKI `.stg`，详见 [`docs/KMI-ABI-CHECK.md`](docs/KMI-ABI-CHECK.md)）。
- 版本号在 `include/config/kernel.release`。


> 最后更新：2026-11-25

---

<a name="guide-susfs"></a>

# BakaSU（原 ReSukiSU）与 SuSFS v2.4.0 落地内核树指南：头文件重建、版本固化与接口校验

> 适用场景：把最新 `Baka-SU/BakaSU`（原 `ReSukiSU/ReSukiSU`，分支 `main`）的 kernel 模块源码「完整落地」到内核树
> `drivers/kernelsu`，并在落地后用仓库内置脚本 `.github/scripts/ksu_pin_version.py` 固化版本号、用 `.github/scripts/ksu_susfs_compat.py` 校验与内核侧 SuSFS v2.4.0 的接口契约。
>
> 本文档总结完整落地中的关键环节：
> 1. **`uapi/` 头文件重建**（`rsync --delete` 落地后必做，否则编译找不到 `uapi/*.h`）
> 2. **版本号固化**（通过 `.github/scripts/ksu_pin_version.py` 固化版本信息，替代早期手动 `fix_kbuild.py`）
> 3. **保持 `-DKSU_NO_PREINIT` 与 `.gitignore` 规则**（防止 HyperOS 上 preinit 劫持 PID 1 导致 bootloop，并忽略构建中间产物）
> 4. **SuSFS v2.4.0 接口契约校验**（运行 `.github/scripts/ksu_susfs_compat.py`）

---

## 0. 路径约定

以下路径可按照实际环境替换：

| 含义 | 路径 / 来源 |
|------|------|
| 源仓库（BakaSU / 原 ReSukiSU） | `https://github.com/Baka-SU/BakaSU`（分支 `main`） |
| SuSFS 官方内核补丁 | `https://gitlab.com/simonpunk/susfs4ksu`（分支 `gki-android15-6.6`，当前 v2.4.0） |
| SuSFS 定制补丁（`55`/`56` 与 `open_redirect`） | `https://github.com/omajili-manbu/susfs4ksu`（分支 `gki-android15-6.6-mod`） |
| 内核树（目标落地位置） | `~/Xiaomi_Rodin_Kernel_Enhance`（分支 `bsp-rodin-v-oss-bp`） |
| 源模块源码目录 | `<源根>/kernel` |
| 落地目标目录 | `<内核根>/drivers/kernelsu` |
| 版本固化脚本（仓库内置） | `.github/scripts/ksu_pin_version.py` |
| 接口契约校验脚本（仓库内置） | `.github/scripts/ksu_susfs_compat.py` |

> Windows 与 WSL 路径映射：`\\wsl.localhost\<发行版>` 对应 `/`，例如
> `\\wsl.localhost\Ubuntu\home\<用户名>\Xiaomi_Rodin_Kernel_Enhance` == `/home/<用户名>/Xiaomi_Rodin_Kernel_Enhance`。

---

## 1. 完整落地源码到内核树

### 1.1 清空并重新拷贝

落地前用 `rsync -a --delete` 让目标严格等于源目录（同步后需补回 `uapi/`、`-DKSU_NO_PREINIT` 与 `.gitignore` 规则）：

```bash
rsync -a --delete <源仓库>/kernel/ <内核根>/drivers/kernelsu/
```

> 要点：`rsync --delete` 会删掉目标中源目录不存在的文件，因此会一并删掉
> `drivers/kernelsu/uapi/` 以及我们本地对 `drivers/kernelsu/.gitignore`、
> `preinit_runner.mk`、`code_generation.mk` 的定制，后续步骤必须逐一补回（自动化工作流 `.github/workflows/sync-resukisu.yml` 已内置相同逻辑）。

### 1.2 同步内核侧 SuSFS 文件（官方 v2.4.0 + 定制 55/56）

落地不只是拷贝 `drivers/kernelsu`，内核侧 SuSFS 文件也须与 BakaSU 所需版本对齐（当前为官方 `simonpunk/susfs4ksu` **v2.4.0**，`gki-android15-6.6` @ `f98f082`）：

```bash
diff <susfs官方>/kernel_patches/include/linux/susfs.h      <内核根>/include/linux/susfs.h
diff <susfs官方>/kernel_patches/include/linux/susfs_def.h  <内核根>/include/linux/susfs_def.h
diff <susfs官方>/kernel_patches/fs/susfs.c                 <内核根>/fs/susfs.c
```

同时须确保 `arch/arm64/configs/gki_defconfig` 启用 `CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y`，并保持 `fs/Makefile` 中的 `CFLAGS_exec.o += -DKSU_NO_PREINIT`（覆盖 SuSFS v2.4.0 在 `fs/exec.c` 中的 `#ifndef KSU_NO_PREINIT` 守卫）。

### 1.3 内核侧补丁（50/55/56）状态

- `50_add_susfs_in_gki-android15-6.6.patch` 来自官方 `simonpunk/susfs4ksu`（v2.4.0），其余定制选择性 SELinux 隐藏补丁 `55_selinux_hook_hide_susfs_artifacts.patch`、`56_selinuxfs_hide_sensitive_av.patch` 与 `open_redirect` 伪装叠加自 `omajili-manbu/susfs4ksu`（`gki-android15-6.6-mod`）。
- 若这些补丁**已打在树里**，常规升级 `drivers/kernelsu` 时不需要重复 `git apply`；升级 SuSFS 主/次版本时才需逐文件比对合入。

> 注意：`susfs4ksu/kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch` 是给**标准**
> KernelSU 用的。BakaSU / ReSukiSU 的 `kernel/` 本身就内置 SUSFS 支持，因此**不要**再应用该补丁。

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
cd <源根>   # 例如上游 BakaSU / ReSukiSU 克隆目录

KSU_LOCAL_VERSION=$(git rev-list --count HEAD)                                # 例 4585
KSU_TAG_NAME=$(git describe --abbrev=0 --tags 2>/dev/null || echo v4.1.0)     # 例 v4.2.0-rc3
KSU_COMMIT_SHA=$(git rev-parse --short=8 HEAD)                                # 例 57b2db60
KSU_BRANCH_NAME=$(git branch --show-current)                                  # 例 main

KSU_VERSION=$((30000 + KSU_LOCAL_VERSION + 700))                              # 例 35285
```

### 3.2 为什么不能用内核树自己的 git（`ksu_pin_version.py` 存在的意义）

Kbuild 默认行为是从 `$(KSU_SRC)` 查 git 拿这些值。但落地后：

- `drivers/kernelsu/` 本身已是内核树 git 仓库的一部分；
- 若让内核树去查询，读到的是**内核树的 commit 数/sha/脏状态**，而非 BakaSU 的。

因此仓库内置脚本 `.github/scripts/ksu_pin_version.py`（替代早期的 `fix_kbuild.py`）会把 Kbuild 的 git 查询分支替换为：`LOCAL_GIT_EXISTS=1` 时查 git（外部模块构建），`LOCAL_GIT_EXISTS=0`（内建树内）时**直接写入固化的版本号**，并内置防 `$(GIT_BIN)` 泄漏断言（兼容上游把 `KSU_TAG_NAME` / `KSU_BRANCH_NAME` 重排到 `KSU_VERSION` 之后的布局）。

### 3.3 `ksu_pin_version.py` 与接口契约校验用法

脚本是**幂等**的（首次落地替换原始块，二次执行原地更新固化值）：

```bash
python3 .github/scripts/ksu_pin_version.py \
  --kbuild drivers/kernelsu/Kbuild \
  --count "$KSU_LOCAL_VERSION" \
  --tag "$KSU_TAG_NAME" \
  --sha8 "$KSU_COMMIT_SHA" \
  --branch "$KSU_BRANCH_NAME"
```

同步后务必补齐 `-DKSU_NO_PREINIT` 与 `.gitignore` 规则，再运行只读接口契约校验器确认 BakaSU 与内核侧 SuSFS v2.4.0 接口完全对齐：

```bash
python3 .github/scripts/ksu_susfs_compat.py --root .
```

替换后 `drivers/kernelsu/Kbuild` 应含：

```makefile
ifeq ($(LOCAL_GIT_EXISTS),1)
$(shell cd $(KSU_SRC); ...)
KSU_LOCAL_VERSION := $(shell ...)
...
else
# Vendored as an in-tree copy of ReSukiSU main @ 57b2db60 (tag v4.2.0-rc3). ...
KSU_LOCAL_VERSION := 4585
KSU_TAG_NAME    := v4.2.0-rc3
KSU_COMMIT_SHA  := 57b2db60
KSU_BRANCH_NAME := main
endif
KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)
```

### 3.4 验证版本

```bash
grep -n 'KSU_VERSION\|KSU_LOCAL_VERSION\|KSU_TAG_NAME\|KSU_COMMIT_SHA\|KSU_BRANCH_NAME' \
  <内核根>/drivers/kernelsu/Kbuild
```

期望：`KSU_LOCAL_VERSION := 4585`、`KSU_TAG_NAME := v4.2.0-rc3`、`KSU_COMMIT_SHA := 57b2db60`、
`KSU_VERSION := $(shell expr 30000 + $(KSU_LOCAL_VERSION) + 700)`（`35285`）。

---

## 4. 落地后自检清单

| 检查项 | 命令 |
|--------|------|
| 无未跟踪构建产物 | `git status --short \| grep '^??'` 为空（确认 `drivers/kernelsu/.gitignore` 保留忽略项） |
| 无意外删除 | `git status --short \| grep '^ D'` 为空 |
| uapi 头齐备 | `ls drivers/kernelsu/uapi/`（6 个 `.h`） |
| 版本固化 | 见 3.4 |
| SuSFS v2.4.0 接口契约 & `-DKSU_NO_PREINIT` | `python3 .github/scripts/ksu_susfs_compat.py --root .` 退出码 `0` |
| 本地构建 + 魔数 + ABI 校验 | `./build-local.sh && scripts/abi-guard.py` 退出码 `0` |

通过后 `git add -A && git commit`。

---

## 5. 当前落地快照（供参考）

| 项 | 值 |
|----|----|
| 源仓库与分支 | `Baka-SU/BakaSU`（原 `ReSukiSU/ReSukiSU`）`main` |
| 源 commit | `57b2db60` |
| tag | `v4.2.0-rc3` |
| KSU_LOCAL_VERSION | `4585` |
| KSU_VERSION（固定值） | `35285`（UAPI 6） |
| 内核侧 SuSFS | 官方 `simonpunk/susfs4ksu` **v2.4.0**（`gki-android15-6.6` @ `f98f082`）+ 定制 `55`/`56` 与 `open_redirect` |
| AOSP 内核基线 | `android15-6.6-lts` @ `8e5968bb7aca`（Linux `6.6.162`，合并提交 `bf641bbe26e9`） |

> 最后更新：2026-11-25

---

<a name="guide-ci"></a>

# ③ 使用 GitHub Actions 工作流编译内核（免本地环境）

**你可以使用工作流编译内核！** 不需要本地 WSL、工具链和几十 GB 源码：仓库自带的
`.github/workflows/build-kernel.yml` 在云端完成 clang-r596125 全量编译、lz4 legacy
打包和 BakaSU（原 ReSukiSU）同提交管理器配对下载，产物下载即用。

## 触发方式

- 手动：仓库 **Actions** → 左侧选 **build-kernel** → **Run workflow** → 分支保持
  `bsp-rodin-v-oss-bp` → 点击运行（需要重建已发布过的版本时勾选 `force`）；
- 命令行：`gh workflow run build-kernel.yml -R <owner>/Xiaomi_Rodin_Kernel_Enhance --ref bsp-rodin-v-oss-bp`；
- 自动（每日，非整点防拥堵）：`sync-android15-6.6-lts`（18:37 UTC / 次日 02:37 UTC+8）与 `sync-resukisu`（18:53 UTC / 次日 02:53 UTC+8）
  成功后经 `workflow_run` 链式触发；另有 19:19 UTC（次日 03:19 UTC+8）的 `schedule`
  兜底一次，防止两个同步工作流失败时当天没有构建。

三者都会先跑一个轻量 `gate`（约 1 分钟）：读取**最新 Release 正文里的
`rodin-build-sha` 标记**，若分支 tip 已经构建并发布过就跳过编译，因此不会因为
多次触发而在同一天重复出包。

## 自动化闭环（每日同步 → 构建 → 发布）

```text
18:37 UTC  sync-android15-6.6-lts  ──┐
18:53 UTC  sync-resukisu           ──┤ 成功后 workflow_run 链式触发
                                     └──────────────┐
                                                    ▼
19:19 UTC  schedule 兜底 ─────────────────► build-kernel (gate → build)
                                                    ▼
                                    GitHub Release v<内核版本>-<UTC时间戳>
```

Release 资产：`Rodin-<版本>-AnyKernel3.zip`（可刷包）+ 与内核固定提交精确匹配的 arm64-v8a 标准版管理器 APK（若同次上游构建提供伪装版，则一并附带）。

## 它在云端做什么

1. 下载 AOSP 预编译 clang-r596125（googlesource `mirror-goog-main-llvm-toolchain-source`
   分支 tarball，失败自动回退固定 commit 直链 / sparse clone）；
2. 按指南①的结论生成配置：`make ARCH=arm64 LLVM=1 gki_defconfig`（只用 gki_defconfig），
   同时校验 `drivers/kernelsu/` 与 SuSFS v2.4.0 接口契约无漂移，再执行 `make ARCH=arm64 LLVM=1 -j"$(nproc)" Image Image.lz4`；
3. 校验 `Image.lz4` 魔数为 `02214c18`（LZ4 legacy）；若不是则自动用 `lz4 -l` 重压并复检；
4. 组装 AnyKernel3（WildKernels gki-2.0）：内核 blob 命名为 `Image`（设备只认这个名字），
   内容为 lz4 legacy 压缩的内核，并写入版本号到 `kernel.string`；
5. 从上游 `ReSukiSU/ReSukiSU`（BakaSU）`main` 分支的 Build Manager CI 中，**严格按内核树 `drivers/kernelsu/Kbuild` 固定的 `KSU_COMMIT_SHA` 精确匹配**同提交构建产物（拒绝回退到错配版本）：必选 arm64-v8a 标准 `release.apk`，同次上游构建提供 `Spoofed-Manager-release.zip` 时再附带 `spoofed-release.apk`。

## 产物（Run 页 artifact + 自动发布的 Release）

| 产物 | 内容与用法 |
|---|---|
| `Rodin-<版本>-AnyKernel3`（artifact） | 可刷包本体。下载得到的 zip 就是 AK3 包（根目录 `anykernel.sh` / `Image` / `META-INF/`），TWRP/KernelSU 直接选中刷入，**无需先解包** |
| `rodin-<版本>-manager`（artifact） | BakaSU（原 ReSukiSU）管理器标准版（arm64-v8a 单 APK） |
| `rodin-<版本>-manager-spoofed`（artifact，按需） | 仅当同次上游 CI run 提供伪装版时生成并上传 |
| `Rodin-<版本>-AnyKernel3.zip` + 匹配 APK（Release） | 同一个构建的正式发布：tag 形如 `v6.6.162-…-20261125-1919`，tag 指向被编译的那个 commit |

## 注意

- 全量 ThinLTO 编译约 35–45 分钟（4 核 runner），任一步失败即中止，日志可直接定位到具体步骤；
- 去重：`gate` 通过 Release 正文的 `rodin-build-sha` 标记识别「这个 commit 已经出过包」，
  同一天多次触发只会产生一个 Release；需要重刷时手动触发并勾选 `force`；
- 管理器版本一致性：**严格按 `KSU_COMMIT_SHA` 精确匹配上游 CI run，不允许回退到不匹配版本**（找不到对应产物则直接失败中止，防止打包错配管理器）；伪装版为可选项，不提供时仅发布标准版；
- 权限：本工作流需要 `contents: write` 才能创建 tag 与 Release（已写在 workflow 里）；若修改任何 `.github/workflows/*.yml`，提交前必须运行 `scripts/check-workflows.py` 校验 YAML 语法与 job 完整性。

> 最后更新：2026-11-25（同步 cron 调度时刻、严格同提交管理器匹配与 SuSFS v2.4.0 契约校验说明）
