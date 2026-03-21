#!/bin/bash
# selfie.sh - 自拍生成

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd")"

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY"
  exit 1
fi

CONTEXT="${1:-在房间里}"
CHANNEL="$2"
CAPTION="${3:-给你看看我现在的样子~}"

# 判断模式
if echo "$CONTEXT" | grep -qiE "(穿 | 衣服 | 穿搭 | 全身 | 镜子)"; then
  MODE="mirror"
  PROMPT="一个年轻女孩在对镜自拍，${CONTEXT}，全身照，镜子反射，自然光线，真实感，高清"
else
  MODE="direct"
  PROMPT="一个年轻女孩的自拍特写，${CONTEXT}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"
fi

echo "📸 模式：$MODE"

RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"wan2.6-image\",
    \"input\": {\"prompt\": \"$PROMPT\"},
    \"parameters\": {\"size\": \"1024x1024\", \"n\": 1}
  }")

IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url // empty')

if [ -z "$IMAGE_URL" ]; then
  echo "❌ 生成失败"
  exit 1
fi

echo "✅ 生成成功：$IMAGE_URL"

if [ -n "$CHANNEL" ]; then
  openclaw message send --action send --channel "$CHANNEL" --message "$CAPTION" --media "$IMAGE_URL"
fi
