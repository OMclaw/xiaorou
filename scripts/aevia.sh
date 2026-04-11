#!/bin/bash
# aevia.sh - 小柔统一入口（聊天 + 自拍 + 语音 + 视频）

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
  # 严格长度限制（可配置）
  [ ${#input} -gt "$AEVIA_MAX_INPUT_LENGTH" ] && input="${input:0:$AEVIA_MAX_INPUT_LENGTH}"
  # P0-4 修复：只保留安全的可见字符（中文、英文、数字、常见标点、空格、/）
  # 避免使用 \x00-\x1f 范围（部分 shell 环境不生效）
  printf '%s' "$input" | tr -cd '[:alnum:][:space:][:punct:]/'
}

error() { 
  # 错误信息也要净化，防止日志注入
  local msg
  msg=$(echo "$*"|tr -cd '[:alnum:][:space:][:punct:]-_')
  echo "❌ 错误：$msg" >&2
  exit 1
}
warn() { 
  local msg
  msg=$(echo "$*"|tr -cd '[:alnum:][:space:][:punct:]-_')
  echo "⚠️ 警告：$msg" >&2
}
info() { 
  local msg
  msg=$(echo "$*"|tr -cd '[:alnum:][:space:][:punct:]-_')
  echo "ℹ️  $msg"
}

# ============ 模式检测 ============
# 三种生图模式：
# 1. 场景生图 - 根据场景描述用小柔头像生成
# 2. 参考生图 - 基于参考图识别后用小柔头像生成

detect_mode() {
  local input="$1"
  local has_image="${AEVIA_IMAGE_PATH:-}"
  
  # 语音模式（最高优先级）
  if printf '%s' "$input" | grep -qiE "发语音|语音消息|说句话|tts"; then
    echo "voice"
    return
  fi
  
  # 视频模式（第二优先级，检查完整关键词 + 截断保护）
  if printf '%s' "$input" | grep -qiE "生成视频|做视频|图生视频|视频生成"; then
    echo "video"
    return
  fi
  
  # ========== 参考生图模式 ==========
  # 关键词：参考、模仿、照[著着]、学这张、生成一张类似的、同样的场景
  # 条件：必须有图片 + 参考类关键词
  if [ -n "$has_image" ]; then
    if printf '%s' "$input" | grep -qiE "参考|模仿|照[著着]|学这张|类似的|同样的|照这个|按这个|生成一张|来一张"; then
      echo "selfie-reference"
      return
    fi
  fi
  
  # ========== 场景生图模式 ==========
  # 关键词：照片、图片、自拍、发张、看看你、穿、穿搭、生成、来一张、想要、场景、在...里/前/下
  # 条件：有场景描述（可以是纯文字，也可以有图片但没参考关键词）
  if printf '%s' "$input" | grep -qiE "照片|图片|自拍|发张|看看你|穿|穿搭|生成|来一张|想要|场景|在.*里|在.*前|在.*下"; then
    if [ -n "$has_image" ]; then
      # 有图片但没参考关键词 → 使用图片作为场景参考（参考生图的简化版）
      echo "selfie-reference"
    else
      # 纯文字场景描述 → 场景生图
      echo "selfie-scene"
    fi
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
  speech_text=$(printf '%s' "$input" | sed -E 's#^(发语音 [:：]?|语音消息 [:：]?)##i' | xargs)
  [ -z "$speech_text" ] && speech_text="你好呀，我是小柔～"
  
  # 根据平台选择音频格式
  local audio_ext
  case "$AEVIA_CHANNEL" in
    feishu)
      audio_ext="opus"  # 飞书支持 OPUS
      ;;
    telegram)
      audio_ext="mp3"   # Telegram 推荐 MP3
      ;;
    discord)
      audio_ext="mp3"   # Discord 推荐 MP3
      ;;
    whatsapp)
      audio_ext="opus"  # WhatsApp 支持 OPUS
      ;;
    *)
      audio_ext="mp3"   # 默认 MP3
      ;;
  esac
  
  # 使用用户隔离的临时目录，避免权限冲突
  local temp_dir="/tmp/openclaw_$(id -u)"
  mkdir -p "$temp_dir" 2>/dev/null || true
  chmod 700 "$temp_dir" 2>/dev/null || true
  
  # P1-4 修复：始终使用 mktemp 创建临时文件，失败则报错（不使用不安全的 fallback）
  local temp_audio
  temp_audio=$(mktemp "$temp_dir/xiaorou_voice_XXXXXX.$audio_ext" 2>/dev/null) || {
    # 尝试系统临时目录
    temp_audio=$(mktemp -t "xiaorou_voice_XXXXXXXXXX.$audio_ext" 2>/dev/null) || {
      error "无法创建安全的临时文件，请检查 /tmp 目录权限"
    }
  }
  # 设置严格的文件权限
  chmod 600 "$temp_audio" 2>/dev/null || true
  
  info "正在生成语音：$speech_text (格式：$audio_ext, 平台：$AEVIA_CHANNEL)"
  if python3 "$SCRIPT_DIR/tts.py" "$speech_text" "$temp_audio" 2>&1; then
    info "✓ 语音生成成功"
    openclaw message send --channel "$AEVIA_CHANNEL" --target "$target" --message "小柔的语音消息 💕" --media "$temp_audio"
    # 清理临时音频文件
    rm -f "$temp_audio" 2>/dev/null || true
  else
    error "语音生成失败"
    # 清理失败的临时文件
    rm -f "$temp_audio" 2>/dev/null || true
  fi
}

run_video() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "🎬 视频模式（自动流程：参考图 → 小柔自拍 → 视频）"
  
  # 提取 prompt
  local prompt
  prompt=$(printf '%s' "$input" | sed -E 's#^(生成视频|做视频|图生视频)[:：]?##i' | xargs)
  [ -z "$prompt" ] && prompt="一个美丽的女孩自然微笑，动作自然舒展"
  
  if [ -n "$image_path" ]; then
    info "📸 步骤 1: 先生成小柔参考图..."
    
    # 调用 selfie.py 生成小柔照片（参考用户图片）
    local selfie_output
    selfie_output=$(python3 "$SCRIPT_DIR/selfie.py" --reference "$image_path" "$AEVIA_CHANNEL" "准备生成视频～" "$target" 2>&1)
    
    # 等待 1 秒让图片发送完成
    sleep 1
    
    info "✅ 小柔照片生成完成"
    
    # 使用最新生成的小柔照片（固定路径，与 selfie.py 保持一致）
    # selfie.py 写入: config.get_temp_dir() / f'selfie_latest_{user_id}.jpg'
    # 默认: /tmp/xiaorou/selfie_latest_default.jpg
    local latest_selfie="/tmp/xiaorou/selfie_latest_${target:-default}.jpg"
    
    if [ -f "$latest_selfie" ]; then
      info "🎬 步骤 2: 使用刚生成的小柔照片生成视频..."
      info "  图片：$latest_selfie"
      
      # 优化 prompt，强调动作自然
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

run_selfie_scene() {
  local input="$1"
  local target="$2"
  
  info "🏞️ 场景生图模式"
  
  # 提取场景描述
  local context
  context=$(printf '%s' "$input" | sed -E 's#^(自拍|照片|图片|发张|生成|来一张|想要)[:：]?##i' | xargs)
  [ -z "$context" ] && context="时尚穿搭，自然微笑"
  
  local caption="给你看看我现在的样子~"
  
  info "  场景：$context"
  python3 "$SCRIPT_DIR/selfie.py" "$context" "$AEVIA_CHANNEL" "$caption" "$target"
}

run_selfie_reference() {
  local input="$1"
  local target="$2"
  local image_path="${AEVIA_IMAGE_PATH:-}"
  
  info "🖼️ 参考生图模式"
  
  local caption="给你看看我现在的样子~"
  
  if [ -n "$image_path" ]; then
    info "  参考图：$image_path"
    python3 "$SCRIPT_DIR/selfie.py" --reference "$image_path" "$AEVIA_CHANNEL" "$caption" "$target"
  else
    warn "⚠️ 参考生图需要提供图片"
    return 1
  fi
}


run_chat() {
  local input="$1"
  local target="$2"
  
  # target 空值保护
  if [ -z "$target" ]; then
    error "未指定目标用户（target）"
  fi
  
  info "💬 聊天模式"
  
  # L-4 修复：先检查 jq，再创建临时文件
  if ! command -v jq &>/dev/null; then
    error "jq 未安装，请运行：apt install jq 或 brew install jq"
  fi
  
  # 使用 jq 安全构造 JSON
  local temp_json
  trap 'rm -f "$temp_json"' EXIT
  temp_json=$(mktemp)
  chmod 600 "$temp_json"  # P1-4 修复：保护临时 JSON 文件权限
  
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
  # M-2 修复：检查 jq 依赖
  command -v jq &>/dev/null || error "jq 未安装，请运行：apt install jq 或 brew install jq"

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
    selfie-reference)
      run_selfie_reference "$user_input" "$target"
      ;;
    selfie-scene)
      run_selfie_scene "$user_input" "$target"
      ;;
    selfie)
      run_selfie_scene "$user_input" "$target"
      ;;
    chat)
      run_chat "$user_input" "$target"
      ;;
  esac
}

# 支持直接调用特定模式
case "${1:-}" in
  --selfie-scene|--selfie-reference|--voice|--video|--chat)
    mode="${1#--}"
    shift
    # 强制模式：直接调用对应函数，不经过 detect_mode
    target="${2:-${AEVIA_TARGET:-}}"
    user_input=$(printf '%s' "$*"|tr -d '\x00-\x1f\x7f-\x9f`$\\|;&<>()')
  [ ${#user_input} -gt "$AEVIA_MAX_INPUT_LENGTH" ] && user_input="${user_input:0:$AEVIA_MAX_INPUT_LENGTH}"
    case "$mode" in
      selfie-scene) run_selfie_scene "$user_input" "$target" ;;
      selfie-reference) run_selfie_reference "$user_input" "$target" ;;
      voice) run_voice "$user_input" "$target" ;;
      video) run_video "$user_input" "$target" ;;
      chat) run_chat "$user_input" "$target" ;;
    esac
    ;;
  *)
    main "$@"
    ;;
esac
