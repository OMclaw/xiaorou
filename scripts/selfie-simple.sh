#!/bin/bash
# selfie-simple.sh - 简化版自拍生成（使用 curl 直接调用 API）
#
# 使用示例:
#   bash scripts/selfie-simple.sh "在咖啡厅喝咖啡" feishu "给你看看我现在的样子~"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"
CHARACTER_IMAGE="$SCRIPT_DIR/../assets/default-character.png"

# ============================================
# 加载 API Key
# ============================================
load_api_key() {
  if [ -n "${DASHSCOPE_API_KEY:-}" ]; then
    return 0
  fi
  
  if [ -f "$CONFIG_FILE" ]; then
    local key
    # 尝试路径 1: skills.entries[].env.DASHSCOPE_API_KEY
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    
    # 尝试路径 2: models.providers.dashscope.apiKey
    if [ -z "$key" ]; then
      key=$(jq -r '.models.providers.dashscope.apiKey // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    fi
    
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  echo "❌ 无法加载 API Key" >&2
  return 1
}

# ============================================
# 构建提示词
# ============================================
build_prompt() {
  local context="$1"
  local mode="direct"
  local prompt=""
  
  # 判断模式
  if echo "$context" | grep -qiE "(穿 | 衣服 | 穿搭 | 全身 | 镜子)"; then
    mode="mirror"
    prompt="在对镜自拍，${context}，全身照，镜子反射，自然光线，真实感，高清"
  else
    mode="direct"
    prompt="${context}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"
  fi
  
  echo "$mode|$prompt"
}

# ============================================
# 图片转 base64
# ============================================
image_to_base64() {
  local image_path="$1"
  base64 -w 0 "$image_path"
}

# ============================================
# 调用 Wan2.6-image API (图生图)
# ============================================
generate_selfie() {
  local prompt="$1"
  local output_dir="/tmp/openclaw/xiaorou"
  mkdir -p "$output_dir"
  
  # 检查头像文件
  if [ ! -f "$CHARACTER_IMAGE" ]; then
    echo "❌ 头像文件不存在：$CHARACTER_IMAGE" >&2
    return 1
  fi
  
  # 将头像转换为 base64
  local image_base64
  image_base64=$(image_to_base64 "$CHARACTER_IMAGE")
  
  # 系统提示词
  local system_prompt="你是一个年轻可爱的女孩，正在用手机自拍。照片要自然、真实、高清。${prompt}"
  
  # 创建临时文件存储请求体
  local temp_file
  temp_file=$(mktemp "$output_dir/request_XXXXXX.json")
  trap "rm -f $temp_file" EXIT
  
  # 构建请求（图生图模式）- 使用临时文件避免命令行过长
  cat > "$temp_file" <<EOF
{
  "model": "wan2.6-image",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          {"image": "data:image/png;base64,${image_base64}"},
          {"text": "${system_prompt}"}
        ]
      }
    ]
  },
  "parameters": {
    "prompt_extend": true,
    "watermark": false,
    "n": 1,
    "enable_interleave": false,
    "size": "2K"
  }
}
EOF
  
  echo "📸 正在生成自拍..." >&2
  
  # 调用 API
  local response
  response=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
    -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$temp_file" --max-time 120) || {
    echo "❌ API 请求失败" >&2
    return 1
  }
  
  # 解析响应
  local image_url
  image_url=$(echo "$response" | jq -r '.output.choices[0].message.content[0].image // empty')
  
  if [ -z "$image_url" ]; then
    echo "❌ 生成失败：$(echo "$response" | jq -r '.message // .code // "未知错误"')" >&2
    echo "响应：$response" >&2
    return 1
  fi
  
  echo "✅ 生成成功！" >&2
  echo "$image_url"
}

# ============================================
# 发送到飞书
# ============================================
send_to_feishu() {
  local image_url="$1"
  local caption="$2"
  local target="${3:-}"
  
  # 如果有 target 参数，使用它；否则让 openclaw 自动推断
  if [ -n "$target" ]; then
    openclaw message send --action send --channel feishu --target "$target" --message "$caption" --media "$image_url" || {
      echo "⚠️ 发送失败" >&2
      return 1
    }
  else
    # 自动推断 target（当前对话）
    openclaw message send --action send --channel feishu --message "$caption" --media "$image_url" || {
      echo "⚠️ 发送失败" >&2
      return 1
    }
  fi
  
  echo "✅ 已发送到飞书" >&2
}

# ============================================
# 主逻辑
# ============================================

# 加载 API Key
if ! load_api_key; then
  exit 1
fi

# 获取参数
CONTEXT="${1:-在咖啡厅喝咖啡}"
CHANNEL="${2:-feishu}"
CAPTION="${3:-给你看看我现在的样子~}"

echo "🎨 场景：$CONTEXT" >&2
echo "📱 频道：$CHANNEL" >&2

# 构建提示词
PROMPT_INFO=$(build_prompt "$CONTEXT")
MODE=$(echo "$PROMPT_INFO" | cut -d'|' -f1)
PROMPT=$(echo "$PROMPT_INFO" | cut -d'|' -f2-)

echo "🎭 模式：$MODE" >&2
echo "💬 提示词：$PROMPT" >&2

# 生成自拍
IMAGE_URL=$(generate_selfie "$PROMPT") || exit 1

echo "🔗 图片 URL: $IMAGE_URL" >&2

# 发送到频道
if [ -n "$CHANNEL" ]; then
  send_to_feishu "$IMAGE_URL" "$CAPTION" || true
fi

# 输出结果
echo ""
echo "✅ 自拍生成完成！"
echo "图片链接：$IMAGE_URL"
