#!/bin/bash
# character.sh - 角色头像生成
#
# 功能:
#   - 使用 Z-image 模型生成角色头像
#   - 自动保存到 assets 目录
#
# 使用示例:
#   bash scripts/character.sh "一个温柔可爱的亚洲女孩头像"
#
# 安全特性:
#   - API Key 安全加载
#   - 输入验证
#   - 路径安全验证

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# ============================================
# 安全函数：加载 API Key
# ============================================
load_api_key() {
  # 优先使用环境变量
  if [ -n "${DASHSCOPE_API_KEY:-}" ]; then
    return 0
  fi
  
  # 从配置文件加载
  if [ -f "$CONFIG_FILE" ]; then
    # 检查文件权限
    local perms
    perms=$(stat -c %a "$CONFIG_FILE" 2>/dev/null || stat -f %Lp "$CONFIG_FILE" 2>/dev/null || echo "unknown")
    if [ "$perms" != "600" ] && [ "$perms" != "400" ] && [ "$perms" != "unknown" ]; then
      echo "⚠️ 警告：配置文件权限不安全，建议运行：chmod 600 $CONFIG_FILE" >&2
    fi
    
    # 安全读取 API Key
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    
    # 验证 API Key 格式
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  return 1
}

# ============================================
# 安全函数：清理输入
# ============================================
sanitize_input() {
  local input="$1"
  local max_len=300
  
  # 长度限制
  if [ ${#input} -gt $max_len ]; then
    echo "⚠️ 输入过长，已截断" >&2
    input="${input:0:$max_len}"
  fi
  
  # 移除危险字符
  input=$(echo "$input" | tr -d '\000-\011\013-\037\177' | sed "s/[\\\`\$(){};|&!]//g")
  
  echo "$input"
}

# ============================================
# 安全函数：验证输出路径
# ============================================
validate_output_path() {
  local path="$1"
  local base_dir="$2"
  
  # 解析绝对路径
  local resolved
  resolved=$(cd "$base_dir" && realpath --relative-to="$base_dir" "$path" 2>/dev/null || echo "__INVALID__")
  
  # 检查是否包含 .. （目录遍历）
  if [[ "$resolved" == *".."* ]] || [[ "$resolved" == "__INVALID__" ]]; then
    return 1
  fi
  
  return 0
}

# ============================================
# 统一错误处理函数
# ============================================
error() {
  echo "❌ 错误：$*" >&2
  exit 1
}

warn() {
  echo "⚠️ 警告：$*" >&2
}

info() {
  echo "ℹ️  $*"
}

# ============================================
# 主逻辑
# ============================================

# 禁用调试模式（防止 API Key 泄露）
set +x

# 加载 API Key
if ! load_api_key; then
  error "无法加载 API Key，请检查配置"
fi

# 获取并验证输入
CHARACTER_DESC_RAW="${1:-一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清}"

# 清理输入
CHARACTER_DESC=$(sanitize_input "$CHARACTER_DESC_RAW")

# 验证输出路径（防止目录遍历）
OUTPUT_FILENAME="default-character.png"
OUTPUT_PATH="$PROJECT_ROOT/assets/$OUTPUT_FILENAME"

if ! validate_output_path "$OUTPUT_PATH" "$PROJECT_ROOT"; then
  error "无效的输出路径"
fi

info "🎨 生成角色头像..."

# 创建临时文件存储 JSON 请求
TEMP_JSON_FILE=$(mktemp)
trap "rm -f $TEMP_JSON_FILE" EXIT

# 构建 JSON 请求
cat > "$TEMP_JSON_FILE" <<EOF
{
  "model": "z-image-turbo",
  "input": {"prompt": "$CHARACTER_DESC"},
  "parameters": {"size": "1024x1024", "n": 1}
}
EOF

# 调用 API
RESPONSE=$(curl -s -f -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON_FILE" 2>/dev/null) || {
  error "API 请求失败"
}

# 解析响应
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url // empty')

if [ -z "$IMAGE_URL" ]; then
  error "生成失败"
fi

# 下载图片
curl -s "$IMAGE_URL" -o "$OUTPUT_PATH" || {
  error "下载图片失败"
}

info "✅ 已保存：$OUTPUT_PATH"
info "🖼️  URL: $IMAGE_URL"
