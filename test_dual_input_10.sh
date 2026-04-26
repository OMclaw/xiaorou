#!/bin/bash
# 双图输入模式测试 - 10 张随机图片

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/dual_input_10_$(date +%Y%m%d_%H%M%S)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ❌${NC} $1"; }

mkdir -p "$OUTPUT_DIR"
log "🚀 开始双图输入模式测试 - 10 张随机图片"
log "📁 输出目录：$OUTPUT_DIR"

# 获取 10 张随机图片
mapfile -t IMAGES < <(find /home/admin/.openclaw/media/inbound -type f \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | shuf | head -10)

TOTAL=${#IMAGES[@]}
SUCCESS=0
FAIL=0

log "📊 找到 $TOTAL 张图片"
echo ""

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
    set +e
    START_TIME=$(date +%s)
    python3 scripts/selfie_v2.py --role-swap "$IMG" "" "双图测试 #$TEST_NUM" "" > "${TEST_DIR}/generate.log" 2>&1
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    set -e
    
    # 分析日志
    if grep -q "生成成功" "${TEST_DIR}/generate.log"; then
        if grep -q "双图输入" "${TEST_DIR}/generate.log"; then
            success "生成成功 (双图模式，耗时：${DURATION}秒)"
            ((SUCCESS++)) || true
        else
            success "生成成功 (耗时：${DURATION}秒)"
            ((SUCCESS++)) || true
        fi
        
        # 显示模式确认
        grep -E "(双图输入 | 图 2 验证)" "${TEST_DIR}/generate.log" | head -3 | sed 's/^/   /'
    else
        error "生成失败 (退出码：$EXIT_CODE)"
        ((FAIL++)) || true
        tail -5 "${TEST_DIR}/generate.log" | sed 's/^/   /'
    fi
    
    # 延迟
    if [ $TEST_NUM -lt $TOTAL ]; then
        log "   ⏳ 等待 3 秒..."
        sleep 3
    fi
done

# 统计报告
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📊 测试完成统计"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_TESTED=$((SUCCESS + FAIL))
if [ $TOTAL_TESTED -gt 0 ]; then
    SUCCESS_RATE=$((SUCCESS * 100 / TOTAL_TESTED))
else
    SUCCESS_RATE=0
fi

echo ""
log "📈 总计：$TOTAL_TESTED/$TOTAL"
success "成功：$SUCCESS"
error "失败：$FAIL"
log "📊 成功率：$SUCCESS_RATE%"
echo ""

# 生成报告文件
cat > "${OUTPUT_DIR}/REPORT.md" << EOF
# 双图输入模式测试报告 - 10 张图片

## 测试时间
$(date)

## 统计结果
- **总测试数**: $TOTAL_TESTED
- **成功**: $SUCCESS ✅
- **失败**: $FAIL ❌
- **成功率**: $SUCCESS_RATE%

## 测试详情
| # | 图片 | 结果 | 耗时 |
|---|------|------|------|
EOF

for i in $(seq 1 $TOTAL); do
    TEST_DIR="${OUTPUT_DIR}/test_${i}"
    if [ -d "$TEST_DIR" ]; then
        IMG_NAME=$(basename "$(ls ${TEST_DIR}/reference.jpg 2>/dev/null || echo "unknown")")
        if grep -q "生成成功" "${TEST_DIR}/generate.log" 2>/dev/null; then
            RESULT="✅ 成功"
        else
            RESULT="❌ 失败"
        fi
        echo "| $i | $IMG_NAME | $RESULT | - |" >> "${OUTPUT_DIR}/REPORT.md"
    fi
done

cat >> "${OUTPUT_DIR}/REPORT.md" << EOF

## 详细日志
见各测试目录的 \`generate.log\` 文件

## 输出位置
\`\`\`
$OUTPUT_DIR/
├── test_1/
│   ├── reference.jpg
│   └── generate.log
...
└── REPORT.md
\`\`\`
EOF

log "📄 测试报告已保存到：${OUTPUT_DIR}/REPORT.md"
log "🎉 双图输入模式测试完成！"

# 显示报告摘要
echo ""
cat "${OUTPUT_DIR}/REPORT.md"
