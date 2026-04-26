#!/bin/bash
# 批量测试脚本 - 随机 30 张图片测试角色替换功能

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/test_output/batch_30_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${OUTPUT_DIR}/test_log.txt"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️${NC} $1" | tee -a "$LOG_FILE"
}

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
echo "=== 批量测试日志 ===" > "$LOG_FILE"
echo "开始时间：$(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

log "🚀 开始批量测试 - 随机 30 张图片"
log "📁 输出目录：$OUTPUT_DIR"

# 获取所有图片列表
mapfile -t ALL_IMAGES < <(find /home/admin/.openclaw/media/inbound -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) 2>/dev/null | head -50)

TOTAL_IMAGES=${#ALL_IMAGES[@]}
log "📊 找到 $TOTAL_IMAGES 张图片"

if [ $TOTAL_IMAGES -lt 30 ]; then
    error "图片数量不足 30 张，实际找到：$TOTAL_IMAGES"
    exit 1
fi

# 随机选择 30 张图片
SELECTED_IMAGES=()
while [ ${#SELECTED_IMAGES[@]} -lt 30 ]; do
    RANDOM_INDEX=$((RANDOM % TOTAL_IMAGES))
    SELECTED_IMAGE="${ALL_IMAGES[$RANDOM_INDEX]}"
    
    # 检查是否已选择
    if [[ ! " ${SELECTED_IMAGES[*]} " =~ " ${SELECTED_IMAGE} " ]]; then
        SELECTED_IMAGES+=("$SELECTED_IMAGE")
    fi
done

log "✅ 已随机选择 30 张图片"
echo "" >> "$LOG_FILE"
echo "=== 测试图片列表 ===" >> "$LOG_FILE"

# 显示选中的图片列表
for i in "${!SELECTED_IMAGES[@]}"; do
    echo "$((i+1)). $(basename "${SELECTED_IMAGES[$i]}")" >> "$LOG_FILE"
done
echo "" >> "$LOG_FILE"

# 测试统计
SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# 开始测试
log "🔥 开始执行测试..."
echo ""

for i in "${!SELECTED_IMAGES[@]}"; do
    IMG_PATH="${SELECTED_IMAGES[$i]}"
    IMG_NAME=$(basename "$IMG_PATH")
    TEST_NUM=$((i+1))
    
    echo ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📸 测试 #$TEST_NUM/30: $IMG_NAME"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 创建单个测试输出目录
    TEST_OUTPUT_DIR="${OUTPUT_DIR}/test_${TEST_NUM}"
    mkdir -p "$TEST_OUTPUT_DIR"
    
    # 复制参考图到测试目录
    cp "$IMG_PATH" "${TEST_OUTPUT_DIR}/reference.jpg"
    
    # 检查图片大小
    IMG_SIZE=$(du -h "$IMG_PATH" | cut -f1)
    log "📦 图片大小：$IMG_SIZE"
    
    # 检查图片维度（如果安装了 file 命令）
    if command -v identify &> /dev/null; then
        IMG_DIM=$(identify -format "%wx%h" "$IMG_PATH" 2>/dev/null || echo "未知")
        log "📐 图片维度：$IMG_DIM"
    fi
    
    # 执行角色替换测试（调用 selfie_v2.py）
    log "🎨 执行角色替换生成..."
    
    # 设置环境变量
    export XIAOROU_CHANNEL="${XIAOROU_CHANNEL:-feishu}"
    export XIAOROU_TARGET="${XIAOROU_TARGET:-}"
    
    # 调用 Python 脚本（不实际发送，只生成）
    cd "$SCRIPT_DIR"
    
    # 检查 Python 脚本是否存在
    if [ ! -f "scripts/selfie_v2.py" ]; then
        warning "⚠️ 脚本不存在：scripts/selfie_v2.py，跳过测试"
        ((SKIP_COUNT++)) || true
        echo "[$TEST_NUM] SKIP - 脚本不存在" >> "${OUTPUT_DIR}/result_summary.txt"
        continue
    fi
    
    # 执行生成（添加超时保护）
    # 用法：python3 selfie_v2.py --role-swap <参考图路径> [频道] [配文] [target]
    set +e
    timeout 120 python3 scripts/selfie_v2.py \
        --role-swap "$IMG_PATH" \
        "" \
        "批量测试 #$TEST_NUM" \
        "" \
        > "${TEST_OUTPUT_DIR}/generate.log" 2>&1
    
    EXIT_CODE=$?
    set -e
    
    # 检查结果
    if [ $EXIT_CODE -eq 0 ]; then
        # 检查是否有输出文件
        OUTPUT_FILES=$(find "$TEST_OUTPUT_DIR" -name "*.jpg" -o -name "*.png" | grep -v "reference.jpg" | wc -l)
        
        if [ $OUTPUT_FILES -gt 0 ]; then
            success "✅ 生成成功 - 输出 $OUTPUT_FILES 张图片"
            ((SUCCESS_COUNT++)) || true
            echo "[$TEST_NUM] SUCCESS - $IMG_NAME" >> "${OUTPUT_DIR}/result_summary.txt"
            
            # 显示生成的文件
            find "$TEST_OUTPUT_DIR" -name "*.jpg" -o -name "*.png" | grep -v "reference.jpg" | while read -r f; do
                log "   📄 $(basename "$f") ($(du -h "$f" | cut -f1))"
            done
        else
            error "❌ 生成失败 - 没有输出文件"
            ((FAIL_COUNT++)) || true
            echo "[$TEST_NUM] FAIL - 无输出文件 - $IMG_NAME" >> "${OUTPUT_DIR}/result_summary.txt"
        fi
    elif [ $EXIT_CODE -eq 124 ]; then
        error "❌ 超时失败 - 超过 120 秒"
        ((FAIL_COUNT++)) || true
        echo "[$TEST_NUM] FAIL - 超时 - $IMG_NAME" >> "${OUTPUT_DIR}/result_summary.txt"
    else
        error "❌ 执行失败 - 退出码：$EXIT_CODE"
        ((FAIL_COUNT++)) || true
        echo "[$TEST_NUM] FAIL - 退出码$EXIT_CODE - $IMG_NAME" >> "${OUTPUT_DIR}/result_summary.txt"
        
        # 显示错误日志最后 10 行
        log "   错误日志:"
        tail -10 "${TEST_OUTPUT_DIR}/generate.log" | sed 's/^/   /'
    fi
    
    # 简单延迟，避免 API 限流
    if [ $TEST_NUM -lt 30 ]; then
        log "⏳ 等待 2 秒..."
        sleep 2
    fi
done

# 生成测试报告
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📊 测试完成统计"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_TESTED=$((SUCCESS_COUNT + FAIL_COUNT + SKIP_COUNT))
SUCCESS_RATE=$(echo "scale=2; $SUCCESS_COUNT * 100 / $TOTAL_TESTED" | bc 2>/dev/null || echo "N/A")

echo ""
log "📈 总计：$TOTAL_TESTED/30"
success "✅ 成功：$SUCCESS_COUNT"
error "❌ 失败：$FAIL_COUNT"
warning "⏭️  跳过：$SKIP_COUNT"
log "📊 成功率：$SUCCESS_RATE%"
echo ""

# 写入报告
cat >> "$LOG_FILE" << EOF

=== 测试报告 ===
测试时间：$(date)
总测试数：$TOTAL_TESTED
成功：$SUCCESS_COUNT
失败：$FAIL_COUNT
跳过：$SKIP_COUNT
成功率：$SUCCESS_RATE%

详细日志见各测试目录的 generate.log 文件
EOF

# 创建汇总报告
cat > "${OUTPUT_DIR}/README.md" << EOF
# 批量测试报告 - 30 张图片

## 测试时间
$(date)

## 统计结果
- **总测试数**: $TOTAL_TESTED
- **成功**: $SUCCESS_COUNT ✅
- **失败**: $FAIL_COUNT ❌
- **跳过**: $SKIP_COUNT ⏭️
- **成功率**: $SUCCESS_RATE%

## 测试图片列表
$(cat "${OUTPUT_DIR}/result_summary.txt")

## 详细日志
见 \`test_log.txt\` 和各测试目录的 \`generate.log\`
EOF

log "📄 测试报告已保存到：${OUTPUT_DIR}/README.md"
log "🎉 批量测试完成！"
