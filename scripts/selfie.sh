#!/bin/bash
# selfie.sh - 自拍生成（基于小柔头像的图生图）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动加载 OpenClaw 配置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  if [ -f "$HOME/.openclaw/openclaw.json" ]; then
    export DASHSCOPE_API_KEY=$(cat "$HOME/.openclaw/openclaw.json" | jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' | head -1)
  fi
fi

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY"
  echo "   在 ~/.openclaw/openclaw.json 中配置"
  exit 1
fi

CONTEXT="${1:-在房间里}"
CHANNEL="$2"
CAPTION="${3:-给你看看我现在的样子~}"

# 调用 Python 脚本
python3 "$SCRIPT_DIR/selfie.py" "$CONTEXT" "$CHANNEL" "$CAPTION"
