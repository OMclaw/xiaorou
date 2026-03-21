#!/bin/bash
# load_openclaw_config.sh - 自动读取 OpenClaw 配置

# 自动从 OpenClaw 配置文件加载 API Key
load_openclaw_config() {
  local config_file="${OPENCLAW_CONFIG_FILE:-$HOME/.openclaw/openclaw.json}"
  
  if [ ! -f "$config_file" ]; then
    echo "⚠️  Warning: OpenClaw config not found at $config_file" >&2
    return 1
  fi
  
  # 读取 dashscope API Key
  local api_key
  api_key=$(jq -r '.models.providers.dashscope.apiKey // empty' "$config_file" 2>/dev/null)
  
  if [ -z "$api_key" ] || [ "$api_key" = "null" ] || [[ "$api_key" == *'$'* ]]; then
    # 尝试 dashscope-us
    api_key=$(jq -r '.models.providers.dashscope-us.apiKey // empty' "$config_file" 2>/dev/null)
  fi
  
  if [ -z "$api_key" ] || [ "$api_key" = "null" ] || [[ "$api_key" == *'$'* ]]; then
    echo "⚠️  Warning: No valid Dashscope API Key found in OpenClaw config" >&2
    return 1
  fi
  
  # 验证 API Key 格式（应该以 sk- 开头）
  if [[ ! "$api_key" =~ ^sk-[a-zA-Z0-9_-]+$ ]]; then
    echo "⚠️  Warning: API Key format may be invalid (should start with 'sk-')" >&2
  fi
  
  # 导出环境变量
  export DASHSCOPE_API_KEY="$api_key"
  echo "✅ Loaded API Key from OpenClaw config" >&2
  return 0
}

# 读取默认角色名（从 SOUL.md 或 IDENTITY.md）
load_character_name() {
  local workspace_dir="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
  local character_name=""
  
  # 优先从 IDENTITY.md 读取 Name 字段
  if [ -f "$workspace_dir/IDENTITY.md" ]; then
    # 尝试匹配 "**Name:** 小柔 (Xiao Rou)" 格式
    # 使用更精确的提取方式，trim 首尾空格
    character_name=$(grep -E "^\*\*Name:\*\*" "$workspace_dir/IDENTITY.md" 2>/dev/null | head -1 | sed 's/^\*\*Name:\*\* *//' | sed 's/ *$//' | xargs)
    
    # 如果没找到，尝试中文名
    if [ -z "$character_name" ]; then
      character_name=$(grep -E "^\*\*中文名\*\*:" "$workspace_dir/IDENTITY.md" 2>/dev/null | head -1 | sed 's/^\*\*中文名\*\*: *//' | sed 's/ *$//' | xargs)
    fi
  fi
  
  # 如果还是没找到，使用默认值"小柔"
  if [ -z "$character_name" ]; then
    character_name="小柔"
  fi
  
  export AEVIA_CHARACTER_NAME="$character_name"
  echo "✅ Loaded character name: $character_name" >&2
}

# 主程序：如果直接运行此脚本，则加载配置
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  load_openclaw_config
  load_character_name
  
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "OpenClaw Config Loaded"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY:0:20}..."
  echo "AEVIA_CHARACTER_NAME: $AEVIA_CHARACTER_NAME"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi
