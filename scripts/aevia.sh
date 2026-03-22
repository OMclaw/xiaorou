#!/bin/bash
# aevia.sh - 主入口（聊天 + 自拍 + 语音）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

load_api_key() {
  [ -n "${DASHSCOPE_API_KEY:-}" ] && return 0
  if [ -f "$CONFIG_FILE" ]; then
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    [ -z "$key" ] && key=$(jq -r '.models.providers.dashscope.apiKey // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  return 1
}

sanitize_input() {
  local input="$1"
  [ ${#input} -gt 500 ] && input="${input:0:500}"
  echo "$input" | tr -d '\000-\011\013-\037\177' | sed "s/[\\\`\$(){};|&!]//g"
}

validate_channel() {
  case "$1" in
    feishu|telegram|discord|whatsapp|"") echo "$1" ;;
    *) echo "⚠️ 未知频道：$1" >&2; echo "" ;;
  esac
}

error() { echo "❌ 错误：$*" >&2; exit 1; }
warn() { echo "⚠️ 警告：$*" >&2; }
info() { echo "ℹ️  $*"; }

set +x
load_api_key || error "无法加载 API Key"

CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"
USER_INPUT_RAW="${1:-}"
CHANNEL_RAW="${2:-}"
TARGET_RAW="${3:-}"

[ -z "$USER_INPUT_RAW" ] && { echo "用法：$0 <消息> [频道] [target]"; exit 0; }

USER_INPUT=$(sanitize_input "$USER_INPUT_RAW")
CHANNEL=$(validate_channel "$CHANNEL_RAW")
TARGET="${TARGET_RAW:-}"

TEMP_FILES=()
cleanup() { for f in "${TEMP_FILES[@]}"; do [ -f "$f" ] && rm -f "$f"; done; }
trap cleanup EXIT

# 语音模式
if echo "$USER_INPUT" | grep -qiE "(发语音 | 语音消息 | 说句话 | 语音回复|voice|tts)"; then
  info "🎙️ 语音模式"
  SPEECH_TEXT=$(echo "$USER_INPUT" | sed -E 's/^(发语音 [:：]?|语音消息 [:：]?|说句话 [:：]?|语音回复 [:：]?)//i' | xargs)
  [ -z "$SPEECH_TEXT" ] && SPEECH_TEXT="你好呀，我是小柔～ 很高兴见到你！"
  
  TEMP_AUDIO="/tmp/openclaw/xiaorou_voice_$(date +%s).opus"
  mkdir -p /tmp/openclaw
  TEMP_FILES+=("$TEMP_AUDIO")
  
  info "正在生成语音：$SPEECH_TEXT"
  if /home/linuxbrew/.linuxbrew/bin/python3.9 "$SCRIPT_DIR/tts.py" "$SPEECH_TEXT" "$TEMP_AUDIO" 2>&1; then
    info "✓ 语音生成成功"
    
    # 获取音频时长（毫秒）
    DURATION_FILE="$TEMP_AUDIO.duration"
    if [ -f "$DURATION_FILE" ]; then
      DURATION_MS=$(cat "$DURATION_FILE")
      info "📊 音频时长：${DURATION_MS}ms"
      rm -f "$DURATION_FILE"
    else
      # 尝试用 ffprobe 获取
      DURATION_MS=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$TEMP_AUDIO" 2>/dev/null)
      if [ -n "$DURATION_MS" ]; then
        DURATION_MS=$(printf "%.0f" "$(echo "$DURATION_MS * 1000" | bc)")
        info "📊 音频时长：${DURATION_MS}ms"
      else
        DURATION_MS=""
        warn "无法获取音频时长"
      fi
    fi
    
    # 构建发送命令
    SEND_CMD="openclaw message send --action send --channel '$CHANNEL'"
    
    # 添加 target 参数（如果提供）
    if [ -n "$TARGET" ]; then
      SEND_CMD="$SEND_CMD --target '$TARGET'"
    fi
    
    SEND_CMD="$SEND_CMD --message '小柔的语音消息 💕' --media '$TEMP_AUDIO' --filename 'voice.opus' --mimeType 'audio/opus'"
    
    # 检查 OpenClaw 是否支持 asVoice 参数
    if openclaw message send --help 2>&1 | grep -q "\-\-asVoice"; then
      SEND_CMD="$SEND_CMD --asVoice"
      info "🎙️ 使用 asVoice 模式发送（显示语音气泡）"
    fi
    
    # 执行发送
    if eval "$SEND_CMD"; then
      info "✓ 语音发送成功"
    else
      warn "发送语音失败"
    fi
  else
    error "语音生成失败"
  fi

# 自拍模式
elif echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张 | 看看你 | 穿 | 穿搭 | 全身 | 镜子|pic|photo|selfie)"; then
  info "📸 自拍模式"
  if [ -n "$TARGET" ]; then
    python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~" "$TARGET"
  else
    python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~"
  fi

# 聊天模式
else
  info "💬 聊天模式"
  TEMP_JSON_FILE=$(mktemp)
  TEMP_FILES+=("$TEMP_JSON_FILE")
  
  cat > "$TEMP_JSON_FILE" <<EOF
{
  "model": "qwen3.5-plus",
  "messages": [
    {"role": "system", "content": "你是${CHARACTER_NAME}，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。"},
    {"role": "user", "content": "$USER_INPUT"}
  ]
}
EOF
  
  RESPONSE=$(curl -s -f -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$TEMP_JSON_FILE" 2>/dev/null) || error "API 请求失败"
  
  REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
  [ -z "$REPLY" ] && error "回复生成失败"
  
  echo "$REPLY"
  
  # 发送消息到频道
  if [ -n "$CHANNEL" ]; then
    SEND_CMD="openclaw message send --action send --channel '$CHANNEL' --message '$REPLY'"
    if [ -n "$TARGET" ]; then
      SEND_CMD="$SEND_CMD --target '$TARGET'"
    fi
    if eval "$SEND_CMD"; then
      info "✓ 消息发送成功"
    else
      warn "发送到频道失败"
    fi
  fi
fi
