#!/bin/bash
# aevia-selfie.sh - 自拍生成
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

USER_CONTEXT="${1:-}"
CHANNEL="${2:-}"
MODE="${3:-auto}"
CAPTION="${4:-给你看看我现在的样子~}"
REFERENCE_IMAGE="${5:-}"

# 加载角色名
if [ -z "$AEVIA_CHARACTER_NAME" ]; then
  source "$SCRIPT_DIR/load_openclaw_config.sh" 2>/dev/null || true
fi
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

if [ -z "$USER_CONTEXT" ]; then
  echo "Usage: $0 <场景描述> [channel] [mode] [caption] [reference_image]"
  echo ""
  echo "Modes:"
  echo "  mirror - 对镜自拍 (适合展示穿搭、全身照)"
  echo "  direct - 直接自拍 (适合特写、场景照)"
  echo "  auto   - 自动选择 (默认)"
  echo ""
  echo "Examples:"
  echo "  $0 '穿粉色连衣裙' '#general' mirror"
  echo "  $0 '在咖啡厅' '#general' direct"
  echo "  $0 '在海边看日落' telegram"
  exit 1
fi

# 输入验证：限制 USER_CONTEXT 长度，防止注入
if [ ${#USER_CONTEXT} -gt 500 ]; then
  echo "❌ Error: Scene description too long (max 500 chars)"
  exit 1
fi

# 移除危险字符（防止 prompt 注入）
USER_CONTEXT=$(echo "$USER_CONTEXT" | tr -d '\n\r\t')

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets"

# Use reference image if provided, otherwise use default character image
# 路径遍历防护：确保引用图片在合法目录内
if [ -n "$REFERENCE_IMAGE" ]; then
  # 解析真实路径
  REAL_PATH=$(realpath -m "$REFERENCE_IMAGE" 2>/dev/null || echo "")
  REAL_ASSETS=$(realpath -m "$ASSETS_DIR" 2>/dev/null || echo "")
  
  # 检查路径是否在 assets 目录内或是绝对路径白名单
  if [ -f "$REFERENCE_IMAGE" ]; then
    if [[ "$REAL_PATH" == "$REAL_ASSETS"/* ]] || [[ "$REFERENCE_IMAGE" == /*assets/* ]]; then
      REF_IMAGE="$REFERENCE_IMAGE"
    else
      echo "❌ Error: Reference image must be in assets directory"
      exit 1
    fi
  else
    echo "❌ Error: Reference image not found: $REFERENCE_IMAGE"
    exit 1
  fi
elif [ -f "$ASSETS_DIR/default-character.png" ]; then
  REF_IMAGE="$ASSETS_DIR/default-character.png"
else
  echo "❌ Error: No reference image found"
  echo "Please provide a reference image or save default-character.png to assets/"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📸 ${CHARACTER_NAME} Selfie Generator (Wan2.6)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode: $MODE"
echo "Context: $USER_CONTEXT"
echo "Reference: $REF_IMAGE"
echo ""

# Auto-detect mode based on keywords
if [ "$MODE" == "auto" ]; then
  if echo "$USER_CONTEXT" | grep -qiE "穿 | 衣服 | 穿搭 | 服装 | 全身 | 镜子 | 对镜"; then
    MODE="mirror"
  else
    MODE="direct"
  fi
  echo "Auto-detected mode: $MODE"
fi

# Build prompt based on mode
if [ "$MODE" == "mirror" ]; then
  PROMPT="一个年轻女孩在对镜自拍，${USER_CONTEXT}，全身照，镜子反射，自然光线，真实感，高清，精致细节"
else
  PROMPT="一个年轻女孩的自拍特写，${USER_CONTEXT}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清，精致细节"
fi

echo "Prompt: $PROMPT"
echo ""

# Call Wan2.6-image API with retry mechanism
MAX_RETRIES=3
RETRY_DELAY=2
ATTEMPT=0
SUCCESS=false

while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
  ATTEMPT=$((ATTEMPT + 1))
  
  if [ $ATTEMPT -gt 1 ]; then
    echo "🔄 Retry attempt $ATTEMPT/$MAX_RETRIES..."
    sleep $RETRY_DELAY
  fi
  
  echo "🎨 Generating image with Wan2.6-image (Attempt $ATTEMPT/$MAX_RETRIES)..."
  
  # Call standalone Python script (API Key 自动从 OpenClaw 配置/环境变量加载)
  RESPONSE=$(python3 "$SCRIPT_DIR/wan26_selfie.py" \
    --timeout 120 \
    "$REF_IMAGE" \
    "$PROMPT")
  
  # Check for errors
  if echo "$RESPONSE" | jq -e '.code' > /dev/null 2>&1; then
    ERROR_CODE=$(echo "$RESPONSE" | jq -r '.code')
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.message')
    
    # Check if it's a retryable error
    if [ "$ERROR_CODE" = "Timeout" ] || [ "$ERROR_CODE" = "RequestError" ]; then
      echo "⚠️  Retryable error: $ERROR_CODE - $ERROR_MSG"
      continue
    fi
    
    echo "❌ API Error: $ERROR_CODE - $ERROR_MSG"
    echo "Response: $RESPONSE"
    exit 1
  fi
  
  SUCCESS=true
done

if [ "$SUCCESS" = false ]; then
  echo "❌ Error: Failed after $MAX_RETRIES attempts"
  exit 1
fi

# Extract image URL from response
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.choices[0].message.content[] | select(.image) | .image')

if [ "$IMAGE_URL" == "null" ] || [ -z "$IMAGE_URL" ]; then
  echo "❌ Error: Failed to generate image"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "✅ Image generated successfully!"
echo "🖼️  URL: $IMAGE_URL"
echo ""

# Send via OpenClaw if channel provided
if [ -n "$CHANNEL" ]; then
  echo "📤 Sending to channel: $CHANNEL"
  
  openclaw message send \
    --action send \
    --channel "$CHANNEL" \
    --message "$CAPTION" \
    --media "$IMAGE_URL"
  
  echo "✅ Sent successfully!"
else
  echo "ℹ️  No channel specified, skipping send"
  echo "   Image URL: $IMAGE_URL"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done! 🦞"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
