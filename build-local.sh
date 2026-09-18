#!/usr/bin/env bash
# ==============================================================================
# Xiaomi Rodin (Redmi Turbo 4 / POCO X7 Pro) 本地极速编译脚本
# 适配环境：WSL2 / Linux (x86_64) + Ryzen 7 9700X (16 线程优化)
# 编译器：Google 预编译 Android Clang 22 (r596125)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

START_TIME=$(date +%s)
CLANG_DIR="/home/server0608/toolchains/clang-r596125"

# 1. 检查本地 clang 工具链
if [ ! -x "$CLANG_DIR/bin/clang" ]; then
    echo "❌ 错误: 未在 $CLANG_DIR 找到可执行的 clang！"
    exit 1
fi

export PATH="$CLANG_DIR/bin:$PATH"
export KBUILD_BUILD_USER="403Forbidden"
export KBUILD_BUILD_HOST="wsl-zen5"

JOBS=$(nproc)
echo "=========================================================="
echo " 🚀 开始本地构建 Xiaomi Rodin GKI 内核"
echo " 🛠️ 编译器: $($CLANG_DIR/bin/clang --version | head -1)"
echo " ⚡ 并行编译线程数: $JOBS"
echo " 👤 编译用户: $KBUILD_BUILD_USER@$KBUILD_BUILD_HOST"
echo "=========================================================="

# 2. 生成 .config (必须只用 gki_defconfig)
echo "📋 [1/4] 生成 gki_defconfig 配置..."
make ARCH=arm64 LLVM=1 gki_defconfig

# 3. 编译内核 Image 与 Image.lz4
echo "🔨 [2/4] 启动全核极速编译 (Image + Image.lz4)..."
make ARCH=arm64 LLVM=1 -j"$JOBS" Image Image.lz4

# 4. 校验并确保 Image.lz4 为 LZ4 Legacy 格式 (魔数 0x184C2102)
echo "🔍 [3/4] 校验 LZ4 Legacy 魔数..."
MAGIC=$(od -An -tx1 -N4 arch/arm64/boot/Image.lz4 | tr -d ' \n')
if [ "$MAGIC" != "02214c18" ]; then
    echo "⚠️ 发现非 legacy 帧格式 (魔数: $MAGIC)，使用 lz4 -l 重新压缩..."
    lz4 -f -l -9 arch/arm64/boot/Image arch/arm64/boot/Image.lz4
    MAGIC=$(od -An -tx1 -N4 arch/arm64/boot/Image.lz4 | tr -d ' \n')
    if [ "$MAGIC" != "02214c18" ]; then
        echo "❌ 错误: 重新压缩后魔数仍不匹配 ($MAGIC)"
        exit 1
    fi
fi
echo "✅ LZ4 Legacy 魔数校验通过: 0x$MAGIC"

# 5. 打包 AnyKernel3 可刷入 Zip
echo "📦 [4/4] 打包 AnyKernel3 刷机包..."
KERNEL_RELEASE=$(cat include/config/kernel.release)
TIMESTAMP=$(date +"%Y%m%d-%H%M")
OUT_DIR="$SCRIPT_DIR/out"
mkdir -p "$OUT_DIR"

BUILD_DIR=$(mktemp -d -t ak3-rodin-XXXXXX)
trap 'rm -rf "$BUILD_DIR"' EXIT

TEMPLATE_DIR="/home/server0608/toolchains/AnyKernel3-template"
if [ ! -d "$TEMPLATE_DIR" ]; then
    git clone --depth=1 -b gki-2.0 https://github.com/WildKernels/AnyKernel3.git "$TEMPLATE_DIR"
    rm -rf "$TEMPLATE_DIR/.git"
fi

cp -r "$TEMPLATE_DIR"/* "$BUILD_DIR"/

# 设备启动只认名为 Image 的 blob；其内容为 lz4 legacy 压缩的内核
cp arch/arm64/boot/Image.lz4 "$BUILD_DIR"/Image
sed -i "s|^kernel.string=.*|kernel.string=Rodin ${KERNEL_RELEASE} (ReSukiSU)|" "$BUILD_DIR"/anykernel.sh

ZIP_NAME="AnyKernel3-Rodin-${KERNEL_RELEASE}-${TIMESTAMP}.zip"
ZIP_PATH="$OUT_DIR/$ZIP_NAME"

(cd "$BUILD_DIR" && zip -r9 "$ZIP_PATH" . -x "*.git*" "README.md" "*placeholder")

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================================="
echo " 🎉 编译与打包圆满完成！"
echo " ⏱️ 编译耗时: ${MINUTES} 分 ${SECONDS} 秒"
echo " 📦 刷机包路径 (WSL):     $ZIP_PATH"
echo " 💻 刷机包路径 (Windows): \\\\wsl.localhost\\Ubuntu${ZIP_PATH//\//\\}"
echo "=========================================================="
