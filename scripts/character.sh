#!/bin/bash
# character.sh - 角色头像生成

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd")"

# 加载配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  source "$SCRIPT_DIR/../load_config.sh" 2>/dev/null || true
fi

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY"
  exit 1
fi

CHARACTER_DESC="${1:-一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清}"
OUTPUT_PATH="$SCRIPT_DIR/../assets/default-character.png"

echo "🎨 生成角色头像..."

RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"z-image-turbo\",
    \"input\": {\"prompt\": \"$CHARACTER_DESC\"},
    \"parameters\": {\"size\": \"1024x1024\", \"n\": 1}
  }")

IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url // empty')

if [ -z "$IMAGE_URL" ]; then
  echo "❌ 生成失败"
  exit 1
fi

curl -s "$IMAGE_URL" -o "$OUTPUT_PATH"
echo "✅ 已保存：$OUTPUT_PATH"
echo "🖼️  URL: $IMAGE_URL"
