#!/bin/bash
# 随机 5 张图片重新生成测试

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/random_5_regenerate_$(date +%Y%m%d_%H%M%S)"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

mkdir -p "$OUTPUT_DIR"
log "🚀 开始随机 5 张图片重新生成测试"
log "📁 输出目录：$OUTPUT_DIR"

# 获取 5 张随机图片
mapfile -t IMAGES < <(find /home/admin/.openclaw/media/inbound -type f \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | shuf | head -5)

TOTAL=${#IMAGES[@]}
SUCCESS=0

for i in "${!IMAGES[@]}"; do
    IMG="${IMAGES[$i]}"
    TEST_NUM=$((i+1))
    IMG_NAME=$(basename "$IMG")
    IMG_SIZE=$(du -h "$IMG" | cut -f1)
    
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📸 测试 #$TEST_NUM/$TOTAL: $IMG_NAME ($IMG_SIZE)"
    
    TEST_DIR="${OUTPUT_DIR}/test_${TEST_NUM}"
    mkdir -p "$TEST_DIR"
    cp "$IMG" "${TEST_DIR}/reference.jpg"
    
    cd "$SCRIPT_DIR"
    
    # 执行生成
    python3 scripts/selfie_v2.py --role-swap "$IMG" "" "随机测试 #$TEST_NUM" "" > "${TEST_DIR}/generate.log" 2>&1
    
    # 检查日志
    if grep -q "生成成功" "${TEST_DIR}/generate.log"; then
        log "✅ 生成成功"
        ((SUCCESS++)) || true
        
        # 显示模式确认
        grep -E "(双图输入 | 图 2 验证)" "${TEST_DIR}/generate.log" | head -3 | sed 's/^/   /'
        
        # 显示生成的文件
        GENERATED_FILE=$(grep "图片已保存到" "${TEST_DIR}/generate.log" | awk -F'：' '{print $2}')
        if [ -n "$GENERATED_FILE" ] && [ -f "$GENERATED_FILE" ]; then
            ls -lh "$GENERATED_FILE" | awk '{print "   📊 文件大小：" $5}'
        fi
    else
        log "❌ 生成失败"
        tail -5 "${TEST_DIR}/generate.log" | sed 's/^/   /'
    fi
    
    # 延迟
    if [ $TEST_NUM -lt $TOTAL ]; then
        log "   ⏳ 等待 3 秒..."
        sleep 3
    fi
done

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📊 测试完成：成功 $SUCCESS/$TOTAL"
log "📁 输出：$OUTPUT_DIR"

# 显示所有生成的图片
echo ""
log "=== 生成的图片列表 ==="
ls -lht /tmp/xiaorou_generated/*.jpg 2>/dev/null | head -5 | awk '{print "   " $9 " (" $5 ")"}'
