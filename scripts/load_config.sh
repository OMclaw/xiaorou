#!/bin/bash
# load_config.sh - 加载 OpenClaw 配置
#
# 功能:
#   - 从环境变量或配置文件加载 API Key
#   - 验证配置文件权限
#   - 验证 API Key 格式
#
# 使用示例:
#   source scripts/load_config.sh
#
# 返回值:
#   0 - 成功加载
#   1 - 加载失败

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# ============================================
# 加载 API Key
# ============================================
load_api_key() {
  # 优先使用环境变量
  if [ -n "${DASHSCOPE_API_KEY:-}" ]; then
    # 验证 API Key 格式
    if [[ "${DASHSCOPE_API_KEY}" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      return 0
    else
      echo "⚠️ 警告：DASHSCOPE_API_KEY 格式可能不正确" >&2
      return 0
    fi
  fi
  
  # 从配置文件加载
  if [ -f "$CONFIG_FILE" ]; then
    # 检查文件权限（仅所有者可读写）
    local perms
    perms=$(stat -c %a "$CONFIG_FILE" 2>/dev/null || stat -f %Lp "$CONFIG_FILE" 2>/dev/null || echo "unknown")
    if [ "$perms" != "600" ] && [ "$perms" != "400" ] && [ "$perms" != "unknown" ]; then
      echo "⚠️ 警告：配置文件权限不安全，建议运行：chmod 600 $CONFIG_FILE" >&2
    fi
    
    # 安全读取 API Key
    local key
    key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    
    # 验证并导出
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  # 加载失败
  echo "❌ 请设置 DASHSCOPE_API_KEY 环境变量" >&2
  echo "   或在 $CONFIG_FILE 中配置" >&2
  return 1
}

# ============================================
# 统一错误处理函数
# ============================================
error() {
  echo "❌ 错误：$*" >&2
  return 1
}

warn() {
  echo "⚠️ 警告：$*" >&2
}

info() {
  echo "ℹ️  $*"
}

# ============================================
# 主逻辑
# ============================================

# 禁用调试模式（防止 API Key 泄露）
set +x

# 加载 API Key
if ! load_api_key; then
  return 1
fi

return 0
