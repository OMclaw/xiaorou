#!/bin/bash
# 快速测试脚本 - 5 张图片验证功能

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/quick_5_$(date +%Y%m%d_%H%M%S)"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

mkdir -p "$OUTPUT_DIR"
log "🚀 开始快速测试 - 5 张图片"

# 获取 5 张图片
mapfile -t IMAGES < <(find /home/admin/.openclaw/media/inbound -type f \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | shuf | head -5)

SUCCESS=0
FAIL=0

for i in "${!IMAGES[@]}"; do
    IMG="${IMAGES[$i]}"
    TEST_NUM=$((i+1))
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📸 测试 #$TEST_NUM/5: $(basename "$IMG")"
    
    TEST_DIR="${OUTPUT_DIR}/test_${TEST_NUM}"
    mkdir -p "$TEST_DIR"
    cp "$IMG" "${TEST_DIR}/reference.jpg"
    
    cd "$SCRIPT_DIR"
    if timeout 180 python3 scripts/selfie_v2.py --role-swap "$IMG" "" "快速测试 #$TEST_NUM" "" > "${TEST_DIR}/generate.log" 2>&1; then
        # 检查日志中是否有"生成成功"
        if grep -q "生成成功" "${TEST_DIR}/generate.log"; then
            log "✅ 成功！(生成 API 调用成功)"
            SUCCESS=$((SUCCESS+1))
        else
            log "❌ 失败 - 日志中无生成成功标记"
            FAIL=$((FAIL+1))
        fi
    else
        log "❌ 失败 - 退出码 $?"
        FAIL=$((FAIL+1))
    fi
done

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📊 结果：成功=$SUCCESS, 失败=$FAIL"
log "📁 输出：$OUTPUT_DIR"
