#!/bin/bash
# tts-simple.sh - 简化版 TTS（使用阿里云 DashScope CosyVoice API）
#
# 使用示例:
#   bash scripts/tts-simple.sh "你好，我是小柔" /tmp/voice.mp3
#   bash scripts/tts-simple.sh "早上好呀" feishu "早安问候"
#
# API 文档：https://help.aliyun.com/zh/model-studio/developer-reference/api-details-25

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# ============================================
# 加载 API Key
# ============================================
load_api_key() {
  if [ -n "${DASHSCOPE_API_KEY:-}" ]; then
    return 0
  fi
  
  if [ -f "$CONFIG_FILE" ]; then
    local key
    # 尝试路径 1: models.providers.dashscope.apiKey
    key=$(jq -r '.models.providers.dashscope.apiKey // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  echo "❌ 无法加载 API Key" >&2
  return 1
}

# ============================================
# TTS 生成（使用 CosyVoice 模型）
# ============================================
generate_speech() {
  local text="$1"
  local output_file="$2"
  local voice="${3:-longanhuan}"
  local model="${4:-cosyvoice-v3-flash}"
  
  # 创建临时文件
  local temp_file
  temp_file=$(mktemp /tmp/tts_XXXXXX.json)
  trap "rm -f $temp_file" EXIT
  
  # 构建请求体（DashScope 标准格式）
  cat > "$temp_file" <<EOF
{
  "model": "${model}",
  "input": {
    "text": "${text}"
  },
  "parameters": {
    "voice": "${voice}",
    "format": "mp3",
    "sample_rate": 24000,
    "volume": 50,
    "rate": 1.0,
    "pitch": 1.0
  }
}
EOF
  
  # 调用 DashScope API（使用标准 TTS 端点）
  local response
  response=$(curl -s -w "\n%{http_code}" -X POST \
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-to-speech/speech-synthesis" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$temp_file") || {
    echo "❌ API 请求失败" >&2
    return 1
  }
  
  # 分离 HTTP 状态码和响应体
  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "200" ]; then
    # 成功，保存音频（响应是二进制音频数据）
    echo "$body" > "$output_file"
    echo "✅ 生成成功：$output_file" >&2
    return 0
  else
    echo "❌ TTS 失败 ($http_code): $body" >&2
    return 1
  fi
}

# ============================================
# 发送到飞书
# ============================================
send_to_feishu() {
  local audio_file="$1"
  local caption="$2"
  
  # 飞书支持发送音频文件
  openclaw message send --action send --channel feishu --message "$caption" --media "$audio_file" || {
    echo "⚠️ 发送失败" >&2
    return 1
  }
  
  echo "✅ 已发送到飞书" >&2
}

# ============================================
# 主逻辑
# ============================================

if ! load_api_key; then
  exit 1
fi

TEXT="${1:-你好，我是小柔}"
OUTPUT="${2:-/tmp/voice.mp3}"
VOICE="${3:-longxiaochun}"
CAPTION="${4:-}"
CHANNEL="${5:-}"

echo "🎙️ TTS 生成中..." >&2
echo "📝 文本：$TEXT" >&2
echo "🎵 音色：$VOICE" >&2

if generate_speech "$TEXT" "$OUTPUT" "$VOICE"; then
  if [ -n "$CHANNEL" ] && [ -n "$CAPTION" ]; then
    send_to_feishu "$OUTPUT" "$CAPTION"
  else
    echo "✅ 音频文件：$OUTPUT"
  fi
else
  exit 1
fi
