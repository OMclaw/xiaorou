#!/bin/bash
# aevia.sh - 小柔统一入口（聊天 + 自拍 + 语音 + 视频）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# 配置（支持环境变量覆盖）
AEVIA_CHANNEL="${AEVIA_CHANNEL:-feishu}"
AEVIA_TARGET="${AEVIA_TARGET:-}"
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

# ============ 工具函数 ============

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
  # 严格长度限制
  [ ${#input} -gt 500 ] && input="${input:0:500}"
  # 只保留安全的字母数字、中文、标点和空格
  # 移除所有控制字符、反引号、美元符号、反斜杠
  echo "$input" | tr -cd '[:alnum:][:space:][:punct:]' | tr -d '`$\\'
}

error() { echo "❌ 错误：$*" >&2; exit 1; }
warn() { echo "⚠️ 警告：$*" >&2; }
info() { echo "ℹ️  $*"; }

# ============ 模式检测 ============

detect_mode() {
  local input="$1"
  local has_image="${AEVIA_IMAGE_PATH:-}"
  
  # 语音模式
  if echo "$input" | grep -qiE "发语音 | 语音消息 | 说句话 | tts"; then
    echo "voice"
    return
  fi
  
  # 视频模式
  if echo "$input" | grep -qiE "生成视频 | 做视频 | 图生视频"; then
    echo "video"
    return
  fi
  
  # 自拍模式（有参考图）
  if [ -n "$has_image" ] && echo "$input" | grep -qiE "参考 | 模仿 | 照著 | 学这张"; then
    echo "selfie-reference"
    return
  fi
  
  # 自拍模式（无参考图）
  if echo "$input" | grep -qiE "照片 | 图片 | 自拍 | 发张 | 看看你 | 穿 | 穿搭"; then
    echo "selfie"
    return
  fi
  
  # 默认：聊天模式
  echo "chat"
}

# ============ 执行模式 ============

run_voice() {
  local input="$1"
  local target="$2"
  
  info "🎙️ 语音模式"
  local speech_text
  speech_text=$(echo "$input" | sed -E 's/^(发语音 [:：]?|语音消息 [:：]?)//i' | xargs)
  [ -z "$speech_text" ] && speech_text="你好呀，我是小柔～"
  
  # 使用 mktemp 创建不可预测的临时文件（避免竞争条件攻击）
  local temp_audio
  temp_audio=$(mktemp "/tmp/openclaw/xiaorou_voice_XXXXXX.opus" 2>/dev/null) || {
    # fallback: 使用时间戳
    temp_audio="/tmp/openclaw/xiaorou_voice_$(date +%s)_$$.opus"
  }
  mkdir -p /tmp/openclaw
  chmod 700 /tmp/openclaw 2>/dev/null || true
  
  info "正在生成语音：$speech_text"
  if python3.11 "$SCRIPT_DIR/tts.py" "$speech_text" "$temp_audio" 2>&1; then
    info "✓ 语音生成成功"
    openclaw message send --channel "$AEVIA_CHANNEL" --target "$target" --message "小柔的语音消息 💕" --media "$temp_audio"
  else
    error "语音生成失败"
  fi
}

run_video() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "🎬 视频模式（自动流程：参考图 → 小柔自拍 → 视频）"
  
  # 提取 prompt
  local prompt
  prompt=$(echo "$input" | sed -E 's/^(生成视频 | 做视频 | 图生视频)[:：]?//i' | xargs)
  [ -z "$prompt" ] && prompt="一个美丽的女孩自然微笑，动作自然舒展"
  
  if [ -n "$image_path" ]; then
    info "📸 步骤 1: 先生成小柔参考图..."
    
    # 调用 selfie.py 生成小柔照片（参考用户图片）
    local selfie_output
    selfie_output=$(python3.11 "$SCRIPT_DIR/selfie.py" --reference "$image_path" "$AEVIA_CHANNEL" "准备生成视频～" "$target" 2>&1)
    
    # 等待 1 秒让图片发送完成
    sleep 1
    
    info "✅ 小柔照片生成完成"
    
    # 使用最新生成的小柔照片（固定路径）
    local latest_selfie="/tmp/openclaw/selfie_latest.jpg"
    
    if [ -f "$latest_selfie" ]; then
      info "🎬 步骤 2: 使用刚生成的小柔照片生成视频..."
      info "  图片：$latest_selfie"
      
      # 优化 prompt，强调动作自然
      local video_prompt="$prompt，动作自然舒展，表情生动，真实摄影感"
      
      python3.11 "$SCRIPT_DIR/generate_video.py" \
        --image "$latest_selfie" \
        --prompt "$video_prompt" \
        --model "wan2.7-i2v" \
        --duration 5 \
        --target "$target"
      
      info "✅ 视频生成完成"
    else
      warn "⚠️ 未找到小柔照片，使用原图生成视频"
      python3.11 "$SCRIPT_DIR/generate_video.py" --image "$image_path" --prompt "$prompt" --target "$target"
    fi
  else
    error "视频生成需要提供图片"
  fi
}

run_selfie() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "📸 自拍模式"
  
  local caption="给你看看我现在的样子~"
  
  if [ -n "$image_path" ]; then
    info "参考图模式"
    python3.11 "$SCRIPT_DIR/selfie.py" --reference "$image_path" "$AEVIA_CHANNEL" "$caption" "$target"
  else
    # 提取场景描述
    local context
    context=$(echo "$input" | sed -E 's/^(自拍 | 照片 | 图片 | 发张)[:：]?//i' | xargs)
    [ -z "$context" ] && context="时尚穿搭，自然微笑"
    
    python3.11 "$SCRIPT_DIR/selfie.py" "$context" "$AEVIA_CHANNEL" "$caption" "$target"
  fi
}

run_chat() {
  local input="$1"
  local target="$2"
  
  info "💬 聊天模式"
  
  # 使用 jq 安全构造 JSON（避免注入攻击）
  local temp_json
  temp_json=$(mktemp)
  
  # 检查是否有 jq
  if command -v jq &>/dev/null; then
    jq -n \
      --arg input "$input" \
      --arg char "$CHARACTER_NAME" \
      '{model: "qwen3.5-plus", messages: [
        {role: "system", content: "你是\($char)，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。"},
        {role: "user", content: $input}
      ]}' > "$temp_json"
  else
    # fallback: 手动转义（如果无 jq）
    local escaped_input
    escaped_input=$(echo "$input" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g' | tr '\n' ' ')
    cat > "$temp_json" <<EOF
{
  "model": "qwen3.5-plus",
  "messages": [
    {"role": "system", "content": "你是${CHARACTER_NAME}，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。"},
    {"role": "user", "content": "$escaped_input"}
  ]
}
EOF
  fi
  
  local response
  response=$(curl -s -f -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$temp_json" 2>/dev/null) || error "API 请求失败"
  
  local reply
  reply=$(echo "$response" | jq -r '.choices[0].message.content // empty')
  [ -z "$reply" ] && error "回复生成失败"
  
  echo "$reply"
  openclaw message send --channel "$AEVIA_CHANNEL" --target "$target" --message "$reply"
  
  rm -f "$temp_json"
}

# ============ 主流程 ============

main() {
  load_api_key || error "无法加载 API Key"
  
  local user_input="${1:-}"
  local target="${2:-${AEVIA_TARGET:-}}"
  
  [ -z "$user_input" ] && { echo "用法：$0 <消息> [target]"; exit 0; }
  
  user_input=$(sanitize_input "$user_input")
  
  # 自动检测模式
  local mode
  mode=$(detect_mode "$user_input")
  
  case "$mode" in
    voice)
      run_voice "$user_input" "$target"
      ;;
    video)
      run_video "$user_input" "$target"
      ;;
    selfie-reference|selfie)
      run_selfie "$user_input" "$target"
      ;;
    chat)
      run_chat "$user_input" "$target"
      ;;
  esac
}

# 支持直接调用特定模式
case "${1:-}" in
  --voice|--video|--selfie|--chat)
    mode="${1#--}"
    shift
    main "$*" "force_$mode"
    ;;
  *)
    main "$@"
    ;;
esac
