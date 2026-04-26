#!/bin/bash
# 双图输入模式测试 - 10 张随机图片 - 保存并发送结果

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/dual_input_10_send_$(date +%Y%m%d_%H%M%S)"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

mkdir -p "$OUTPUT_DIR"
log "🚀 开始双图输入模式测试 - 10 张随机图片（保存结果）"
log "📁 输出目录：$OUTPUT_DIR"

# 获取 10 张随机图片
mapfile -t IMAGES < <(find /home/admin/.openclaw/media/inbound -type f \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | shuf | head -10)

TOTAL=${#IMAGES[@]}
SUCCESS=0

for i in "${!IMAGES[@]}"; do
    IMG="${IMAGES[$i]}"
    TEST_NUM=$((i+1))
    IMG_NAME=$(basename "$IMG")
    
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📸 测试 #$TEST_NUM/$TOTAL: $IMG_NAME"
    
    TEST_DIR="${OUTPUT_DIR}/test_${TEST_NUM}"
    mkdir -p "$TEST_DIR"
    cp "$IMG" "${TEST_DIR}/reference.jpg"
    
    cd "$SCRIPT_DIR"
    
    # 执行生成
    python3 scripts/selfie_v2.py --role-swap "$IMG" "" "双图测试 #$TEST_NUM" "" > "${TEST_DIR}/generate.log" 2>&1
    
    # 检查日志
    if grep -q "生成成功" "${TEST_DIR}/generate.log"; then
        log "✅ 生成成功"
        ((SUCCESS++)) || true
        
        # 提取生成的图片 URL 并下载（从日志中）
        # 由于脚本不保存，需要手动从 API 响应获取
        # 这里只记录成功
        echo "测试 #$TEST_NUM: 成功" >> "${OUTPUT_DIR}/results.txt"
    else
        log "❌ 生成失败"
        echo "测试 #$TEST_NUM: 失败" >> "${OUTPUT_DIR}/results.txt"
    fi
    
    # 延迟
    if [ $TEST_NUM -lt $TOTAL ]; then
        sleep 3
    fi
done

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📊 测试完成：成功 $SUCCESS/$TOTAL"
log "📁 输出：$OUTPUT_DIR"
