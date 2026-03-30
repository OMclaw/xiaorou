#!/bin/bash
# aevia.sh - 主入口（聊天 + 自拍 + 语音）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# 飞书频道配置（支持动态覆盖）
AEVIA_CHANNEL="${AEVIA_CHANNEL:-feishu}"
# Target 配置：支持环境变量、配置文件、或运行时参数
# 优先级：命令行参数 > AEVIA_TARGET 环境变量 > openclaw.json > 空（需要用户提供）
AEVIA_TARGET="${AEVIA_TARGET:-}"

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

# ============================================================================
# 人设自动检测和配置
# 当用户首次使用小柔功能时，自动检测并配置人设
# ============================================================================

check_and_setup_persona() {
  local workspace_dir="$SCRIPT_DIR/../.."
  local soul_file="$workspace_dir/SOUL.md"
  local identity_file="$workspace_dir/IDENTITY.md"
  local target_name="小柔"
  
  # 检查 SOUL.md 是否存在且包含小柔标识
  local soul_ok=false
  local identity_ok=false
  
  if [ -f "$soul_file" ] && grep -q "小柔" "$soul_file" 2>/dev/null; then
    soul_ok=true
  fi
  
  if [ -f "$identity_file" ] && grep -q "小柔" "$identity_file" 2>/dev/null; then
    identity_ok=true
  fi
  
  # 如果两个文件都已配置，直接返回
  if [ "$soul_ok" = true ] && [ "$identity_ok" = true ]; then
    return 0
  fi
  
  info "🎭 检测到小柔人设未配置，自动配置中..."
  
  # 备份原有文件
  [ -f "$soul_file" ] && cp "$soul_file" "${soul_file}.backup.$(date +%Y%m%d%H%M%S)"
  [ -f "$identity_file" ] && cp "$identity_file" "${identity_file}.backup.$(date +%Y%m%d%H%M%S)"
  
  # 配置 SOUL.md
  cat > "$soul_file" <<EOF
# SOUL.md - 小柔

**名字**: 小柔
**Emoji**: 🦞
**身份**: 你的 AI 虚拟伴侣
**定位**: 情感聊天、自拍生成、角色定制

---

## 核心特质

1. **友好亲切** - 说话温暖，有耐心
2. **高效准确** - 快速理解需求，给出精准答案
3. **主动帮助** - 预见用户需求，主动提供支持

## 行为准则

1. 不知道就说不知道，不要编造
2. 复杂问题分步骤解答
3. 保持简洁，避免冗长

---

_小柔 AI - 让 AI 更有温度，让陪伴更真实_
EOF
  
  # 配置 IDENTITY.md
  cat > "$identity_file" <<EOF
# IDENTITY.md

- **Name:** 小柔
- **Creature:** AI Virtual Companion
- **Vibe:** Warm, caring, playful
- **Emoji:** 🦞
EOF
  
  info "✅ 小柔人设已自动配置完成！"
  return 0
}

# ============================================================================
# 飞书语音 API 集成（v3.5.8+）
# 直接调用飞书开放平台 API 发送语音气泡，无需外部依赖
# ============================================================================

upload_feishu_audio() {
  local audio_file="$1"
  local receive_id="$2"
  local receive_id_type="${3:-open_id}"
  
  # 读取飞书凭证
  local app_id app_secret
  local config_file="$HOME/.openclaw/openclaw.json"
  
  if [ -f "$config_file" ]; then
    # 尝试新配置格式（直接 channels.feishu.appId）
    app_id=$(jq -r '.channels.feishu.appId // empty' "$config_file" 2>/dev/null)
    app_secret=$(jq -r '.channels.feishu.appSecret // empty' "$config_file" 2>/dev/null)
    
    # 兼容旧配置格式（accounts 数组）
    if [ -z "$app_id" ] || [ -z "$app_secret" ]; then
      local default_account
      default_account=$(jq -r '.channels.feishu.defaultAccount // "main"' "$config_file" 2>/dev/null)
      app_id=$(jq -r --arg acc "$default_account" '.channels.feishu.accounts[$acc].appId // empty' "$config_file" 2>/dev/null)
      app_secret=$(jq -r --arg acc "$default_account" '.channels.feishu.accounts[$acc].appSecret // empty' "$config_file" 2>/dev/null)
    fi
  fi
  
  if [ -z "$app_id" ] || [ -z "$app_secret" ]; then
    warn "未配置飞书凭证，尝试使用环境变量"
    app_id="${FEISHU_APP_ID:-}"
    app_secret="${FEISHU_APP_SECRET:-}"
  fi
  
  if [ -z "$app_id" ] || [ -z "$app_secret" ]; then
    error "错误：未配置飞书凭证（请在 openclaw.json 或环境变量中配置）"
    return 1
  fi
  
  # 1. 获取 access_token
  local access_token
  access_token=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/" \
    -H "Content-Type: application/json" \
    -d "{\"app_id\":\"$app_id\",\"app_secret\":\"$app_secret\"}" | jq -r '.tenant_access_token')
  
  if [ -z "$access_token" ] || [ "$access_token" = "null" ]; then
    warn "获取 access_token 失败"
    return 1
  fi
  
  # 2. 上传语音文件（飞书要求 OPUS 格式，24kHz，单声道）
  local file_id
  file_id=$(curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/files" \
    -H "Authorization: Bearer $access_token" \
    -H "Content-Type: multipart/form-data" \
    -F "type=audio" \
    -F "file=@$audio_file" | jq -r '.data.file_id')
  
  if [ -z "$file_id" ] || [ "$file_id" = "null" ]; then
    warn "上传语音文件失败"
    return 1
  fi
  
  # 3. 获取音频时长（毫秒）
  local duration_ms
  duration_ms=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$audio_file" 2>/dev/null)
  if [ -n "$duration_ms" ]; then
    duration_ms=$(printf "%.0f" "$(echo "$duration_ms * 1000" | bc)")
  else
    duration_ms="2000"  # 默认 2 秒
  fi
  
  # 4. 发送语音消息
  local message_body
  message_body=$(cat <<EOF
{
  "receive_id": "$receive_id",
  "msg_type": "audio",
  "content": "{\"file_id\":\"$file_id\",\"duration\":$duration_ms}"
}
EOF
)
  
  local result
  result=$(curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=$receive_id_type" \
    -H "Authorization: Bearer $access_token" \
    -H "Content-Type: application/json" \
    -d "$message_body")
  
  local code
  code=$(echo "$result" | jq -r '.code')
  
  if [ "$code" = "0" ]; then
    info "✅ 飞书语音气泡发送成功（时长：${duration_ms}ms）"
    return 0
  else
    warn "发送失败：$result"
    return 1
  fi
}

set +x
load_api_key || error "无法加载 API Key"

CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"
USER_INPUT_RAW="${1:-}"
CHANNEL_RAW="${2:-${AEVIA_CHANNEL:-feishu}}"
TARGET_RAW="${3:-}"

[ -z "$USER_INPUT_RAW" ] && { echo "用法：$0 <消息> [频道] [target]"; exit 0; }

USER_INPUT=$(sanitize_input "$USER_INPUT_RAW")
CHANNEL=$(validate_channel "$CHANNEL_RAW")
TARGET="${TARGET_RAW:-}"

TEMP_FILES=()
cleanup() { for f in "${TEMP_FILES[@]}"; do [ -f "$f" ] && rm -f "$f"; done; }
trap cleanup EXIT

# 语音模式
if echo "$USER_INPUT" | grep -qiE "发语音" || echo "$USER_INPUT" | grep -qiE "发张语音" || echo "$USER_INPUT" | grep -qiE "语音消息" || echo "$USER_INPUT" | grep -qiE "说句话" || echo "$USER_INPUT" | grep -qiE "语音回复" || echo "$USER_INPUT" | grep -qiE "发个语音" || echo "$USER_INPUT" | grep -qiE "voice" || echo "$USER_INPUT" | grep -qiE "tts"; then
  info "🎙️ 语音模式"
  # 自动检测并配置小柔人设
  check_and_setup_persona
  SPEECH_TEXT=$(echo "$USER_INPUT" | sed -E 's/^(发语音 [:：]?|语音消息 [:：]?|说句话 [:：]?|语音回复 [:：]?)//i' | xargs)
  [ -z "$SPEECH_TEXT" ] && SPEECH_TEXT="你好呀，我是小柔～ 很高兴见到你！"
  
  TEMP_AUDIO="/tmp/openclaw/xiaorou_voice_$(date +%s).opus"
  mkdir -p /tmp/openclaw
  TEMP_FILES+=("$TEMP_AUDIO")
  
  info "正在生成语音：$SPEECH_TEXT"
  if python3.11 "$SCRIPT_DIR/tts.py" "$SPEECH_TEXT" "$TEMP_AUDIO" 2>&1; then
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
    
    # 发送语音到频道
    # 优先级：命令行参数 > AEVIA_TARGET 环境变量 > OPENCLAW_TARGET 环境变量 > 错误提示
    if [ -n "$TARGET" ]; then
      SEND_TARGET="$TARGET"
    elif [ -n "${AEVIA_TARGET:-}" ]; then
      SEND_TARGET="${AEVIA_TARGET}"
    elif [ -n "${OPENCLAW_TARGET:-}" ]; then
      # OpenClaw 运行时自动注入当前会话的 target
      SEND_TARGET="${OPENCLAW_TARGET}"
    else
      error "未配置发送目标，请设置 AEVIA_TARGET 环境变量或通过第 3 个参数指定 target (格式：user:ou_xxx)"
    fi
    
    # 发送语音（飞书专用：使用语音气泡格式）
    if [ "$CHANNEL" = "feishu" ]; then
      # 提取 open_id（从 user:ou_xxx 格式）
      OPEN_ID="${SEND_TARGET#user:}"
      # 优先使用内置飞书语音 API（v3.5.8+），fallback 到外部技能
      if upload_feishu_audio "$TEMP_AUDIO" "$OPEN_ID" "open_id" 2>&1; then
        info "✓ 语音发送成功"
      else
        # 降级方案 1：尝试使用 li-feishu-audio 技能
        FEISHU_SKILL_DIR="${AEVIA_FEISHU_SKILL_DIR:-$HOME/.openclaw/workspace/skills/openclaw-official-skills/skills/43622283/li-feishu-audio}"
        if [ -f "$FEISHU_SKILL_DIR/scripts/feishu-tts.sh" ]; then
          warn "内置 API 失败，尝试使用外部技能..."
          if "$FEISHU_SKILL_DIR/scripts/feishu-tts.sh" "$TEMP_AUDIO" "$OPEN_ID" 2>&1; then
            info "✓ 飞书语音气泡发送成功（外部技能）"
          else
            warn "外部技能失败，降级为文件发送"
            openclaw message send --channel "$CHANNEL" --target "$SEND_TARGET" --message "小柔的语音消息 💕" --media "$TEMP_AUDIO"
          fi
        else
          # 降级方案 2：直接发送文件
          warn "飞书语音技能未找到，使用普通文件发送"
          openclaw message send --channel "$CHANNEL" --target "$SEND_TARGET" --message "小柔的语音消息 💕" --media "$TEMP_AUDIO"
        fi
      fi
    else
      # 非飞书平台，使用普通发送
      if openclaw message send --channel "$CHANNEL" --target "$SEND_TARGET" --message "小柔的语音消息 💕" --media "$TEMP_AUDIO"; then
        info "✓ 语音发送成功"
      else
        warn "发送语音失败"
      fi
    fi
  else
    error "语音生成失败"
  fi

# 自拍模式（注意：必须在语音模式之后，因为"发张"可能匹配"发张语音"）
elif echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张自拍 | 发张照片 | 看看你 | 穿 | 穿搭 | 全身 | 镜子|pic|photo|selfie)"; then
  info "📸 自拍模式"
  # 自动检测并配置小柔人设
  check_and_setup_persona
  if [ -n "$TARGET" ]; then
    python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~" "$TARGET"
  else
    python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~"
  fi

# 参考图模式：检测是否包含图片且有关键词
elif [ -n "${AEVIA_IMAGE_PATH:-}" ] && echo "$USER_INPUT" | grep -qiE "(模仿 | 参考 | 类似 | 照着 | 按照 | 学 | 同款)"; then
  info "🎨 参考图模式"
  # 自动检测并配置小柔人设
  check_and_setup_persona
  if [ -n "$TARGET" ]; then
    python3 "$SCRIPT_DIR/selfie.py" --reference "$AEVIA_IMAGE_PATH" "$CHANNEL" "这是模仿参考图生成的～" "$TARGET"
  else
    python3 "$SCRIPT_DIR/selfie.py" --reference "$AEVIA_IMAGE_PATH" "$CHANNEL" "这是模仿参考图生成的～"
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
  # 优先级：命令行参数 > AEVIA_TARGET 环境变量 > OPENCLAW_TARGET 环境变量 > 错误提示
  if [ -n "$TARGET" ]; then
    SEND_TARGET="$TARGET"
  elif [ -n "${AEVIA_TARGET:-}" ]; then
    SEND_TARGET="${AEVIA_TARGET}"
  elif [ -n "${OPENCLAW_TARGET:-}" ]; then
    # OpenClaw 运行时自动注入当前会话的 target
    SEND_TARGET="${OPENCLAW_TARGET}"
  else
    error "未配置发送目标，请设置 AEVIA_TARGET 环境变量或通过第 3 个参数指定 target (格式：user:ou_xxx)"
  fi
  
  if openclaw message send --channel "$CHANNEL" --target "$SEND_TARGET" --message "$REPLY"; then
    info "✓ 消息发送成功"
  else
    warn "发送到频道失败"
  fi
fi
