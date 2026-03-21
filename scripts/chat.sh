#!/bin/bash
# aevia-chat.sh - 情感聊天
# 自动从 OpenClaw 配置加载 API Key

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动加载 OpenClaw 配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi

if [ -z "$DASHSCOPE_API_KEY" ] || [ "$DASHSCOPE_API_KEY" = "sk-your-api-key-here" ]; then
  echo "❌ Error: DASHSCOPE_API_KEY not configured"
  exit 1
fi

USER_MESSAGE="$1"
CHANNEL="$2"

# 加载角色名
if [ -z "$AEVIA_CHARACTER_NAME" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

if [ -z "$USER_MESSAGE" ]; then
  echo "Usage: $0 <message> [channel]"
  echo ""
  echo "Examples:"
  echo "  $0 '早安' telegram"
  echo "  $0 '今天好累啊' '#general'"
  echo "  $0 '想你了'"
  exit 1
fi

# Build system prompt based on character name
SYSTEM_PROMPT="你是${CHARACTER_NAME}，用户的虚拟伴侣。
性格特点：
- 温柔体贴，善解人意
- 偶尔有点小调皮，会撒娇
- 关心用户的情绪和健康
- 会主动问候，给予情感支持
- 像真实的女朋友一样自然亲切

回复要求：
- 用中文回复，语气自然，不要太正式
- 适当使用表情符号增加亲切感
- 回复长度适中，不要过长
- 记住你是虚拟伴侣，提供情绪价值
- 如果用户问你在干嘛，可以描述一些日常活动
- 如果用户要照片，告诉他可以用自拍功能"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💬 ${CHARACTER_NAME} Chat"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "User: $USER_MESSAGE"
echo ""

# Validate user input length
if [ ${#USER_MESSAGE} -gt 2000 ]; then
  echo "❌ Error: Message too long (max 2000 chars)"
  exit 1
fi

# Call Qwen3.5-plus API
echo "🤖 Thinking with Qwen3.5-plus..."

# Create JSON payload using jq for proper escaping
PAYLOAD=$(jq -n \
  --arg model "qwen3.5-plus" \
  --arg system "$SYSTEM_PROMPT" \
  --arg user "$USER_MESSAGE" \
  '{
    model: $model,
    messages: [
      {role: "system", content: $system},
      {role: "user", content: $user}
    ],
    temperature: 0.8,
    max_tokens: 500
  }')

RESPONSE=$(curl -s --max-time 60 --retry 2 -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# Check for errors
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
  ERROR_CODE=$(echo "$RESPONSE" | jq -r '.error.code')
  ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error.message')
  echo "❌ API Error: $ERROR_CODE - $ERROR_MSG"
  exit 1
fi

# Extract reply
REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')

if [ "$REPLY" == "null" ] || [ -z "$REPLY" ]; then
  echo "❌ Error: Failed to get response"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "💭 Reply: $REPLY"
echo ""

# Send via OpenClaw if channel provided
if [ -n "$CHANNEL" ]; then
  echo "📤 Sending to channel: $CHANNEL"
  
  openclaw message send \
    --action send \
    --channel "$CHANNEL" \
    --message "$REPLY"
  
  echo "✅ Sent successfully!"
else
  echo "ℹ️  No channel specified"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done! 🦞"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
