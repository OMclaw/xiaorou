#!/bin/bash
# aevia-character.sh - 角色头像生成
# 自动从 OpenClaw 配置加载 API Key

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动加载 OpenClaw 配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi

CHARACTER_DESC="${1:-}"
OUTPUT_DIR="$SCRIPT_DIR/../assets"

# 加载角色名
if [ -z "$AEVIA_CHARACTER_NAME" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

# 检查 API Key，如果没有则退出（移除交互式输入）
if [ -z "$DASHSCOPE_API_KEY" ] || [ "$DASHSCOPE_API_KEY" = "sk-your-api-key-here" ]; then
  echo "❌ DASHSCOPE_API_KEY not configured"
  echo ""
  echo "Please get your API key from: https://bailian.console.aliyun.com/"
  echo ""
  echo "Then either:"
  echo "  1. Set in OpenClaw config (~/.openclaw/openclaw.json) - Recommended"
  echo "  2. Export: export DASHSCOPE_API_KEY=sk-xxx"
  echo "  3. Create .env file in project directory"
  echo ""
  echo "❌ API key required. Exiting."
  exit 1
fi

# 验证 API Key 格式
if [[ ! "$DASHSCOPE_API_KEY" =~ ^sk-[a-zA-Z0-9_-]+$ ]]; then
  echo "❌ Invalid API Key format. Should start with 'sk-'"
  exit 1
fi

# Default description if not provided
if [ -z "$CHARACTER_DESC" ]; then
  CHARACTER_DESC="一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清，精致，二次元风格"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 ${CHARACTER_NAME} Character Generator"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Description: $CHARACTER_DESC"
echo ""

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Call Z-image API (using multimodal endpoint)
echo "🎨 Generating character avatar with Z-image..."

PAYLOAD=$(jq -n \
  --arg model "z-image-turbo" \
  --arg prompt "$CHARACTER_DESC" \
  '{
    model: $model,
    input: {
      messages: [{
        role: "user",
        content: [{ text: $prompt }]
      }]
    },
    parameters: {
      size: "1024*1024",
      n: 1
    }
  }')

# 使用临时文件传递 Authorization header，避免在命令行中暴露 API Key
AUTH_HEADER_FILE=$(mktemp)
echo "Authorization: Bearer $DASHSCOPE_API_KEY" > "$AUTH_HEADER_FILE"
trap "rm -f $AUTH_HEADER_FILE" EXIT

RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
  -H "@$AUTH_HEADER_FILE" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# Check for errors
if echo "$RESPONSE" | jq -e '.code' > /dev/null 2>&1; then
  ERROR_CODE=$(echo "$RESPONSE" | jq -r '.code')
  ERROR_MSG=$(echo "$RESPONSE" | jq -r '.message')
  echo "❌ API Error: $ERROR_CODE - $ERROR_MSG"
  echo "Response: $RESPONSE"
  exit 1
fi

# Extract image URL (from multimodal response format)
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.choices[0].message.content[] | select(.image) | .image')

if [ "$IMAGE_URL" == "null" ] || [ -z "$IMAGE_URL" ]; then
  echo "❌ Error: Failed to generate character"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "✅ Character avatar generated!"
echo "🖼️  URL: $IMAGE_URL"
echo ""

# Download and save locally
OUTPUT_PATH="$OUTPUT_DIR/character.png"
echo "💾 Downloading to: $OUTPUT_PATH"

curl -s "$IMAGE_URL" -o "$OUTPUT_PATH"

if [ -f "$OUTPUT_PATH" ]; then
  echo "✅ Saved successfully!"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📋 Next Steps:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "1. Update your openclaw.json config:"
  echo '   "AEVIA_REFERENCE_IMAGE_URL": "'$IMAGE_URL'"'
  echo ""
  echo "2. Or upload the image to a CDN and use that URL"
  echo ""
  echo "3. Local file saved at: $OUTPUT_PATH"
  echo ""
else
  echo "❌ Failed to save file"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done! 🦞"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
