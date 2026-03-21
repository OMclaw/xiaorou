#!/bin/bash
# aevia.sh - Aevia 主入口 (智能判断聊天/自拍)
# 自动从 OpenClaw 配置加载 API Key

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动加载 OpenClaw 配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi

# 如果还是没找到，报错
if [ -z "$DASHSCOPE_API_KEY" ] || [ "$DASHSCOPE_API_KEY" = "sk-your-api-key-here" ]; then
  echo "❌ Error: DASHSCOPE_API_KEY not configured"
  echo ""
  echo "Solutions:"
  echo "  1. Set in OpenClaw config (~/.openclaw/openclaw.json) - Preferred"
  echo "  2. Export environment variable: export DASHSCOPE_API_KEY=sk-xxx"
  echo "  3. Create .env file in aevia directory"
  echo ""
  exit 1
fi

USER_INPUT="$1"
CHANNEL="$2"

# 加载角色名（从 OpenClaw 配置或环境变量）
if [ -z "$AEVIA_CHARACTER_NAME" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

if [ -z "$USER_INPUT" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🦞 ${CHARACTER_NAME} - 虚拟伴侣"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Usage: $0 <message> [channel]"
  echo ""
  echo "Examples:"
  echo "  $0 '早安' telegram"
  echo "  $0 '发张自拍' '#general'"
  echo "  $0 '想你了'"
  echo "  $0 '穿粉色连衣裙的照片'"
  echo ""
  echo "Features:"
  echo "  💬 情感聊天 - 自动使用 Qwen3.5-plus"
  echo "  📸 自拍生成 - 自动使用 Wan2.6-image"
  echo "  🎨 角色定制 - 运行 character.sh"
  echo ""
  exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 ${CHARACTER_NAME} Processing..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Input: $USER_INPUT"
echo ""

# Detect intent: is this a request for a photo/selfie?
is_photo_request=false

# Check for photo-related keywords (optimized matching range)
# 使用更精确的匹配，避免误判
if echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张 | 看看你 | 长什么样 | 穿.*衣服 | 穿搭 | 服装 | 全身 | 镜子 | 对镜 | pic|photo|selfie|image|picture|show me|want.*pic|send.*pic)"; then
  is_photo_request=true
fi

# Also check if it's a "what are you doing" type question (can respond with photo)
# 但排除纯聊天场景
if echo "$USER_INPUT" | grep -qiE "^(在干嘛 | 在哪里 | 在做什么 | what are you doing|where are you)"; then
  is_photo_request=true
fi

if [ "$is_photo_request" = true ]; then
  echo "📸 Detected: Photo request"
  echo ""
  
  # Extract context for the photo
  # If the input is just "发张自拍", use a default context
  if echo "$USER_INPUT" | grep -qiE "^(发张自拍 | 照片 | 自拍 | show me)$"; then
    PHOTO_CONTEXT="今天的心情很好，阳光明媚"
  else
    PHOTO_CONTEXT="$USER_INPUT"
  fi
  
  echo "Photo context: $PHOTO_CONTEXT"
  echo ""
  
  # Call selfie script
  bash "$SCRIPT_DIR/selfie.sh" "$PHOTO_CONTEXT" "$CHANNEL" "auto" "给你看看我现在的样子~"
else
  echo "💬 Detected: Chat message"
  echo ""
  
  # Call chat script
  bash "$SCRIPT_DIR/chat.sh" "$USER_INPUT" "$CHANNEL"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done! 🦞"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
