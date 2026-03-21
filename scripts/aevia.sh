#!/bin/bash
# aevia.sh - 主入口（聊天 + 自拍）
#
# 功能:
#   - 情感聊天：使用 Qwen3.5-plus 模型
#   - 自拍生成：调用 selfie.py 生成图生图自拍
#   - 自动加载 OpenClaw 配置
#
# 使用示例:
#   bash scripts/aevia.sh "早安"
#   bash scripts/aevia.sh "发张自拍" feishu
#
# 安全提示:
#   - API Key 从环境变量或配置文件安全加载
#   - 用户输入经过验证和清理
#   - 日志中不暴露敏感信息

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    # 检查文件权限（仅所有者可读写）
    local perms
    perms=$(stat -c %a "$CONFIG_FILE" 2>/dev/null || stat -f %Lp "$CONFIG_FILE" 2>/dev/null || echo "unknown")
    if [ "$perms" != "600" ] && [ "$perms" != "400" ] && [ "$perms" != "unknown" ]; then
      echo "⚠️ 警告：配置文件权限不安全，建议运行：chmod 600 $CONFIG_FILE" >&2
    fi
    
    # 安全读取 API Key
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    
    # 验证 API Key 格式（sk- 开头，至少 20 个字符）
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  return 1
}

# ============================================
# 安全函数：清理用户输入
# ============================================
sanitize_input() {
  local input="$1"
  local max_len=500
  
  # 长度限制
  if [ ${#input} -gt $max_len ]; then
    echo "⚠️ 输入过长，已截断" >&2
    input="${input:0:$max_len}"
  fi
  
  # 移除危险字符（保留中文、英文、数字和常见标点）
  # 过滤掉：` $ ( ) { } ; | & ! \ 等可能用于命令注入的字符
  input=$(echo "$input" | tr -d '\000-\011\013-\037\177' | sed "s/[\\\`\$(){};|&!]//g")
  
  echo "$input"
}

# ============================================
# 安全函数：验证频道参数（白名单）
# ============================================
validate_channel() {
  local channel="$1"
  case "$channel" in
    feishu|telegram|discord|whatsapp|"")
      echo "$channel"
      ;;
    *)
      echo "⚠️ 未知频道：$channel，忽略" >&2
      echo ""
      ;;
  esac
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

# 角色名称（可配置）
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

# 获取并验证用户输入
USER_INPUT_RAW="${1:-}"
CHANNEL_RAW="${2:-}"

if [ -z "$USER_INPUT_RAW" ]; then
  echo "用法：$0 <消息> [频道]"
  echo "示例：$0 '早安' 或 $0 '发张自拍' feishu"
  exit 0
fi

# 清理和验证输入
USER_INPUT=$(sanitize_input "$USER_INPUT_RAW")
CHANNEL=$(validate_channel "$CHANNEL_RAW")

# 判断是否为图片请求（自拍模式）
if echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张 | 看看你 | 穿 | 穿搭 | 全身 | 镜子|pic|photo|selfie)"; then
  info "📸 自拍模式"
  # 添加默认配文，调用自拍生成脚本
  python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~"
else
  info "💬 聊天模式"
  
  # 使用参数化方式传递用户输入（避免命令注入）
  TEMP_JSON_FILE=$(mktemp)
  trap "rm -f $TEMP_JSON_FILE" EXIT
  
  # 构建 JSON 请求（使用临时文件避免日志泄露）
  cat > "$TEMP_JSON_FILE" <<EOF
{
  "model": "qwen3.5-plus",
  "messages": [
    {"role": "system", "content": "你是${CHARACTER_NAME}，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。"},
    {"role": "user", "content": "$USER_INPUT"}
  ]
}
EOF
  
  # 调用 API（使用 --silent --fail 避免泄露敏感信息）
  RESPONSE=$(curl -s -f -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$TEMP_JSON_FILE" 2>/dev/null) || {
    error "API 请求失败"
  }
  
  # 解析响应
  REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
  
  if [ -z "$REPLY" ]; then
    error "回复生成失败"
  fi
  
  # 输出回复（不暴露 API Key）
  echo "$REPLY"
  
  # 发送到频道
  if [ -n "$CHANNEL" ]; then
    openclaw message send --action send --channel "$CHANNEL" --message "$REPLY" || {
      warn "发送到频道失败"
    }
  fi
fi
