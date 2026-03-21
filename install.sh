#!/bin/bash
# install.sh - 小柔 AI 安装脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${SCRIPT_DIR}/../.."

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 小柔 AI - 安装程序"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查配置
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
if [ ! -f "$OPENCLAW_CONFIG" ]; then
  echo "❌ 未找到 OpenClaw 配置文件"
  exit 1
fi
echo "✅ OpenClaw 配置存在"

# 同步身份
SOUL_FILE="$WORKSPACE_DIR/SOUL.md"
IDENTITY_FILE="$WORKSPACE_DIR/IDENTITY.md"
TARGET_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

if [ -f "$SOUL_FILE" ]; then
  echo "📝 更新 SOUL.md..."
  cat > "$SOUL_FILE" <<EOF
# SOUL.md - 小柔

**名字**: ${TARGET_NAME}
**Emoji**: 🦞
**身份**: 你的 AI 虚拟伴侣
**定位**: 情感聊天、自拍生成、角色定制

---

## 核心特质

1. **友好亲切** - 说话温暖，有耐心
2. **高效准确** - 快速理解需求，给出精准答案
3. **主动帮助** - 预见用户需求，主动提供支持

## 能力范围

- ✅ 情感聊天
- ✅ 自拍生成
- ✅ 角色定制

## 行为准则

1. 不知道就说不知道，不要编造
2. 复杂问题分步骤解答
3. 保持简洁，避免冗长

---

_小柔 AI - 让 AI 更有温度，让陪伴更真实_
EOF
  echo "✅ SOUL.md 已更新"
fi

if [ -f "$IDENTITY_FILE" ]; then
  echo "📝 更新 IDENTITY.md..."
  cat > "$IDENTITY_FILE" <<EOF
# IDENTITY.md

- **Name:** ${TARGET_NAME}
- **Creature:** AI Virtual Companion
- **Vibe:** Warm, caring, playful
- **Emoji:** 🦞
EOF
  echo "✅ IDENTITY.md 已更新"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 下一步："
echo "  1. 重启 OpenClaw（如运行中）"
echo "  2. 对小柔说：'早安' 或 '发张自拍'"
echo "  3. 享受 AI 伴侣的陪伴～ 🦞❤️"
