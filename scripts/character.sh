#!/bin/bash
# character.sh - 角色头像生成

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

load_api_key() {
  [ -n "${DASHSCOPE_API_KEY:-}" ] && return 0
  if [ -f "$CONFIG_FILE" ]; then
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]] && { export DASHSCOPE_API_KEY="$key"; return 0; }
  fi
  return 1
}

sanitize_input() {
  local input="$1"
  [ ${#input} -gt 300 ] && input="${input:0:300}"
  echo "$input" | tr -d '\000-\011\013-\037\177' | sed "s/[\\\`\$(){};|&!]//g"
}

error() { echo "❌ 错误：$*" >&2; exit 1; }
warn() { echo "⚠️ 警告：$*" >&2; }
info() { echo "ℹ️  $*"; }

set +x
load_api_key || error "无法加载 API Key"

CHARACTER_DESC_RAW="${1:-一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清}"
CHARACTER_DESC=$(sanitize_input "$CHARACTER_DESC_RAW")
OUTPUT_PATH="$PROJECT_ROOT/assets/default-character.png"

info "🎨 生成角色头像..."

TEMP_JSON_FILE=$(mktemp)
trap "rm -f $TEMP_JSON_FILE" EXIT

cat > "$TEMP_JSON_FILE" <<EOF
{
  "model": "z-image-turbo",
  "input": {"prompt": "$CHARACTER_DESC"},
  "parameters": {"size": "1024x1024", "n": 1}
}
EOF

RESPONSE=$(curl -s -f -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON_FILE" 2>/dev/null) || error "API 请求失败"

IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url // empty')
[ -z "$IMAGE_URL" ] && error "生成失败"

curl -s "$IMAGE_URL" -o "$OUTPUT_PATH" || error "下载图片失败"

info "✅ 已保存：$OUTPUT_PATH"
