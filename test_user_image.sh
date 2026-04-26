#!/bin/bash
# 用户图片测试脚本 - 保存生成的图片

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/user_images_$(date +%Y%m%d_%H%M%S)"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

mkdir -p "$OUTPUT_DIR"
log "🚀 开始用户图片测试"
log "📁 输出目录：$OUTPUT_DIR"

# 从参数获取图片路径
IMAGE_PATH="$1"
if [ -z "$IMAGE_PATH" ]; then
    log "❌ 请提供图片路径"
    exit 1
fi

IMAGE_NAME=$(basename "$IMAGE_PATH")
log "📸 测试图片：$IMAGE_NAME"

# 复制参考图到输出目录
cp "$IMAGE_PATH" "${OUTPUT_DIR}/reference.jpg"

# 执行生成
cd "$SCRIPT_DIR"
log "🎨 执行角色替换生成..."

python3 scripts/selfie_v2.py --role-swap "$IMAGE_PATH" "" "用户图片测试" "" > "${OUTPUT_DIR}/generate.log" 2>&1

# 检查日志
if grep -q "生成成功" "${OUTPUT_DIR}/generate.log"; then
    log "✅ 生成成功！"
    log "📄 日志：${OUTPUT_DIR}/generate.log"
    log "📁 参考图：${OUTPUT_DIR}/reference.jpg"
    
    # 显示日志摘要
    echo ""
    log "=== 日志摘要 ==="
    grep -E "(API Key|验证通过 | 生成 | 模式)" "${OUTPUT_DIR}/generate.log" | head -10
else
    log "❌ 生成失败"
    tail -20 "${OUTPUT_DIR}/generate.log"
fi
