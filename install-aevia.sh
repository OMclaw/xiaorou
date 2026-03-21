#!/bin/bash
# install-aevia.sh - 小柔 AI 一键安装脚本

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 小柔 AI - 一键安装"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

OPENCLAW_SKILLS_DIR="$HOME/.openclaw/workspace/skills"

if [ ! -d "$OPENCLAW_SKILLS_DIR" ]; then
  echo "❌ 未找到 OpenClaw skills 目录"
  exit 1
fi

INSTALL_DIR="$OPENCLAW_SKILLS_DIR/xiaorou"

if [ -d "$INSTALL_DIR" ]; then
  echo "🔄 检测到已安装，正在更新..."
  cd "$INSTALL_DIR"
  git pull origin main
else
  echo "📦 正在下载..."
  cd "$OPENCLAW_SKILLS_DIR"
  git clone https://github.com/OMclaw/xiaorou.git
  cd xiaorou
fi

echo ""
echo "🚀 正在安装..."
bash install.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 下一步："
echo "  1. 重启 OpenClaw（如运行中）"
echo "  2. 对小柔说：'早安' 或 '发张自拍'"
echo "  3. 享受 AI 伴侣的陪伴～ 🦞❤️"
