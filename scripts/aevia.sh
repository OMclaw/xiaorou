#!/bin/bash
# aevia.sh - 小柔统一入口（聊天 + 参考生图 + 修图 + 视频 + 语音）
# 版本：v2.0 重构版 - 2026-04-26

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# 配置（支持环境变量覆盖）
AEVIA_CHANNEL="${AEVIA_CHANNEL:-feishu}"
AEVIA_TARGET="${AEVIA_TARGET:-}"
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"
AEVIA_MAX_INPUT_LENGTH="${AEVIA_MAX_INPUT_LENGTH:-500}"

# ============ 工具函数 ============

load_api_key() {
  [ -n "${DASHSCOPE_API_KEY:-}" ] && return 0
  if [ -f "$CONFIG_FILE" ]; then
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null|head -1)
    [ -z "$key" ] && key=$(jq -r '.models.providers.dashscope.apiKey // empty' "$CONFIG_FILE" 2>/dev/null|head -1)
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  return 1
}

sanitize_input() {
  local input="$1"
  [ ${#input} -gt "$AEVIA_MAX_INPUT_LENGTH" ] && input="${input:0:$AEVIA_MAX_INPUT_LENGTH}"
  printf '%s' "$input" | tr -cd '[:alnum:][:space:]/,.!?，。！？、：；（）《》-'
}

error() { 
  local msg
  msg=$(printf '%s' "$*" | tr -cd '[:alnum:][:space:][:punct:]-_')
  printf '%s\n' "❌ 错误：$msg" >&2
  exit 1
}

warn() { 
  local msg
  msg=$(printf '%s' "$*" | tr -cd '[:alnum:][:space:][:punct:]-_')
  printf '%s\n' "⚠️ 警告：$msg" >&2
}

info() { 
  local msg
  msg=$(printf '%s' "$*" | tr -cd '[:alnum:][:space:][:punct:]-_')
  printf '%s\n' "ℹ️  $msg"
}

# ============ 模式检测 ============
# 五种能力模式（按优先级排序）：
# 1. 语音模式 - 发语音、语音消息、用语音说
# 2. 视频模式 - 生成视频、图生视频、动起来
# 3. 修图模式 - 修图、编辑、修改、把衣服换成（需要图片）
# 4. 参考生图模式 - 生图、参考、模仿、类似的（需要图片）
# 5. 聊天模式 - 默认

detect_mode() {
  local input="$1"
  local has_image="${AEVIA_IMAGE_PATH:-}"
  
  # ========== 1. 语音模式（最高优先级） ==========
  if printf '%s' "$input" | grep -qiE "发语音 | 语音消息 | 用语音说 | 说句话|tts"; then
    echo "voice"
    return
  fi
  
  # ========== 2. 视频模式（第二优先级） ==========
  if printf '%s' "$input" | grep -qiE "生视频 | 做视频 | 图生视频 | 视频生成 | 动起来"; then
    echo "video"
    return
  fi
  
  # ========== 3. 修图模式（第三优先级） ==========
  # 关键词：修图、编辑、修改、把衣服换成、换个、改成、换成、调整一下
  # 条件：必须有图片 + 修图类关键词
  if [ -n "$has_image" ]; then
    if printf '%s' "$input" | grep -qiE "修图 | 编辑 | 修改 | 把衣服换成 | 换个 | 改成 | 换成 | 调整一下"; then
      echo "inpaint"
      return
    fi
  fi
  
  # ========== 4. 参考生图模式（第四优先级） ==========
  # 关键词：生图、参考、模仿、照着、学这张、类似的、同样的、生成一张、来一张
  # 条件：必须有图片 + 生图/参考类关键词
  if [ -n "$has_image" ]; then
    if printf '%s' "$input" | grep -qiE "生图 | 参考 | 模仿 | 照 [著着]|学这张 | 类似的 | 同样的 | 照这个 | 按这个 | 生成一张 | 来一张"; then
      echo "selfie-reference"
      return
    fi
  fi
  
  # ========== 5. 聊天模式（默认） ==========
  echo "chat"
}

# ============ 执行模式 ============

run_voice() {
  local input="$1"
  local target="$2"
  
  info "🎙️ 语音模式"
  local speech_text
  speech_text=$(printf '%s' "$input" | sed -E 's#^(发语音 [:：]?|语音消息 [:：]?|用语音说 [:：]?)##i' | xargs)
  [ -z "$speech_text" ] && speech_text="你好呀，我是小柔～"
  
  local audio_ext
  case "$AEVIA_CHANNEL" in
    feishu) audio_ext="opus" ;;
    telegram|discord|whatsapp) audio_ext="mp3" ;;
    *) audio_ext="mp3" ;;
  esac
  
  local temp_dir="/tmp/openclaw_$(id -u)"
  mkdir -p "$temp_dir" 2>/dev/null || true
  
  local temp_audio
  temp_audio=$(mktemp "$temp_dir/xiaorou_voice_XXXXXX.$audio_ext" 2>/dev/null) || {
    temp_audio=$(mktemp -t "xiaorou_voice_XXXXXXXXXX.$audio_ext" 2>/dev/null) || {
      error "无法创建安全的临时文件"
    }
  }
  chmod 600 "$temp_audio" 2>/dev/null || true
  
  info "正在生成语音：$speech_text"
  if python3 "$SCRIPT_DIR/tts.py" "$speech_text" "$temp_audio" 2>&1; then
    info "✓ 语音生成成功"
    openclaw message send --channel "$AEVIA_CHANNEL" --target "$target" --message "小柔的语音消息 💕" --media "$temp_audio"
    rm -f "$temp_audio" 2>/dev/null || true
  else
    error "语音生成失败"
    rm -f "$temp_audio" 2>/dev/null || true
  fi
}

run_video() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "🎬 视频模式"
  
  local prompt
  prompt=$(printf '%s' "$input" | sed -E 's#^(小柔生视频 | 生成视频 | 做视频 | 图生视频)[:：]?##i' | xargs)
  [ -z "$prompt" ] && prompt="一个美丽的女孩自然微笑，动作自然舒展"
  
  if [ -n "$image_path" ]; then
    info "📸 步骤 1: 先生成小柔参考图..."
    local selfie_output
    selfie_output=$(python3 "$SCRIPT_DIR/selfie_v2.py" --role-swap "$image_path" "$AEVIA_CHANNEL" "准备生成视频～" "$target" 2>&1)
    sleep 1
    
    local latest_selfie="/tmp/xiaorou/selfie_latest_${target:-default}.jpg"
    if [ -f "$latest_selfie" ]; then
      info "🎬 步骤 2: 使用小柔照片生成视频..."
      local video_prompt="$prompt，动作自然舒展，表情生动，真实摄影感"
      python3 "$SCRIPT_DIR/generate_video.py" \
        --image "$latest_selfie" \
        --prompt "$video_prompt" \
        --model "wan2.6-i2v" \
        --duration 5 \
        --target "$target"
      info "✅ 视频生成完成"
    else
      warn "⚠️ 未找到小柔照片，使用原图生成视频"
      python3 "$SCRIPT_DIR/generate_video.py" --image "$image_path" --prompt "$prompt" --target "$target"
    fi
  else
    error "视频生成需要提供图片"
  fi
}

run_inpaint() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "✏️ 修图模式（服饰局部重绘）"
  
  if [ -n "$image_path" ]; then
    # 提取修图指令
    local instruction
    instruction=$(printf '%s' "$input" | sed -E 's#^(小柔修图 | 修图 | 帮我修图)[:：]?##i' | xargs)
    [ -z "$instruction" ] && instruction="修改一下服装"
    
    info "  原图：$image_path"
    info "  指令：$instruction"
    
    # 调用 selfie_inpaint.py 进行局部重绘
    python3 "$SCRIPT_DIR/selfie_inpaint.py" "$image_path" "$instruction" "$AEVIA_CHANNEL" "$target"
    info "✅ 修图完成"
  else
    error "修图需要提供图片"
  fi
}

run_selfie_reference() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "🖼️ 参考生图模式"
  
  local caption="给你看看我现在的样子~"
  
  if [ -n "$image_path" ]; then
    info "  参考图：$image_path（双图输入）"
    python3 "$SCRIPT_DIR/selfie_v2.py" --role-swap "$image_path" "$AEVIA_CHANNEL" "$caption" "$target"
  else
    warn "⚠️ 参考生图需要提供图片"
    return 1
  fi
}

run_chat() {
  local input="$1"
  local target="$2"
  
  if [ -z "$target" ]; then
    error "未指定目标用户（target）"
  fi
  
  info "💬 聊天模式"
  
  if ! command -v jq &>/dev/null; then
    error "jq 未安装"
  fi
  
  local temp_json
  temp_json=$(mktemp)
  chmod 600 "$temp_json"
  trap 'rm -f "$temp_json"' EXIT
  
  jq -n \
    --arg input "$input" \
    --arg char "$CHARACTER_NAME" \
    '{model: "qwen3.5-plus", messages: [
      {role: "system", content: "你是\($char)，用户的虚拟伴侣。性格温柔体贴，善解人意。用中文回复，语气自然亲切。"},
      {role: "user", content: $input}
    ]}' > "$temp_json"
  
  local response
  response=$(curl --tlsv1.2 --max-redirs 3 --max-time 120 -f -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$temp_json" 2>/dev/null) || error "API 请求失败"
  
  local reply
  reply=$(echo "$response" | jq -r '.choices[0].message.content // empty')
  [ -z "$reply" ] && error "回复生成失败"
  
  echo "$reply"
  openclaw message send --channel "$AEVIA_CHANNEL" --target "$target" --message "$reply"
}

# ============ 主流程 ============

main() {
  command -v jq &>/dev/null || error "jq 未安装"
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
    inpaint)
      run_inpaint "$user_input" "$target"
      ;;
    selfie-reference)
      run_selfie_reference "$user_input" "$target"
      ;;
    chat)
      run_chat "$user_input" "$target"
      ;;
  esac
}

# 支持直接调用特定模式
case "${1:-}" in
  --selfie-reference|--voice|--video|--inpaint|--chat)
    mode="${1#--}"
    shift
    target="${2:-${AEVIA_TARGET:-}}"
    load_api_key || error "无法加载 API Key"
    case "$mode" in
      voice) run_voice "${1:-}" "$target" ;;
      video) run_video "${1:-}" "$target" ;;
      inpaint) run_inpaint "${1:-}" "$target" ;;
      selfie-reference) run_selfie_reference "${1:-}" "$target" ;;
      chat) run_chat "${1:-}" "$target" ;;
    esac
    ;;
  --help|-h)
    echo "小柔 AI - 统一入口脚本"
    echo ""
    echo "用法："
    echo "  $0 <消息> [target]           # 自动检测模式"
    echo "  $0 --voice <消息> [target]   # 强制语音模式"
    echo "  $0 --video <消息> [target]   # 强制视频模式"
    echo "  $0 --inpaint <消息> [target] # 强制修图模式"
    echo "  $0 --selfie-reference <消息> [target]  # 强制参考生图"
    echo "  $0 --chat <消息> [target]    # 强制聊天模式"
    echo ""
    echo "五种能力："
    echo "  1. 小柔生图   - 参考图生图（发送图片 + '小柔生图'）"
    echo "  2. 小柔修图   - 图像编辑（发送图片 + '小柔修图：把衣服换成...'）"
    echo "  3. 小柔生视频 - 视频生成（发送图片 + '小柔生视频：...'）"
    echo "  4. 小柔发语音 - TTS 语音（'小柔发语音：...'）"
    echo "  5. 小柔聊天   - 情感对话（任意对话）"
    exit 0
    ;;
  *)
    main "$@"
    ;;
esac
