#!/bin/bash
# aevia.sh - 主入口（聊天 + 自拍）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd")"

# 自动加载 OpenClaw 配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  if [ -f "$HOME/.openclaw/openclaw.json" ]; then
    export DASHSCOPE_API_KEY=$(cat "$HOME/.openclaw/openclaw.json" | jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' | head -1)
  fi
fi

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY"
  echo "   在 ~/.openclaw/openclaw.json 中配置"
  exit 1
fi

CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"
USER_INPUT="$1"
CHANNEL="$2"

if [ -z "$USER_INPUT" ]; then
  echo "用法：$0 <消息> [频道]"
  echo "示例：$0 '早安' 或 $0 '发张自拍' feishu"
  exit 0
fi

# 判断是否为图片请求
if echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张 | 看看你 | 穿 | 穿搭 | 全身 | 镜子|pic|photo|selfie)"; then
  echo "📸 自拍模式"
  bash "$SCRIPT_DIR/selfie.sh" "$USER_INPUT" "$CHANNEL"
else
  echo "💬 聊天模式"
  
  RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"qwen3.5-plus\",
      \"messages\": [
        {\"role\": \"system\", \"content\": \"你是${CHARACTER_NAME}，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。\"},
        {\"role\": \"user\", \"content\": \"$USER_INPUT\"}
      ]
    }")
  
  REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
  
  if [ -z "$REPLY" ]; then
    echo "❌ 回复生成失败"
    exit 1
  fi
  
  echo "$REPLY"
  
  if [ -n "$CHANNEL" ]; then
    openclaw message send --action send --channel "$CHANNEL" --message "$REPLY"
  fi
fi
