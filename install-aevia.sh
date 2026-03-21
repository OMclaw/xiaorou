#!/bin/bash
# install-aevia.sh - 小柔 AI 一键安装脚本
# 
# 🔒 安全安装方式（推荐）:
#   git clone https://github.com/OMclaw/xiaorou.git
#   cd xiaorou && bash install-aevia.sh
#
# ⚠️ 快速安装方式（有风险，仅用于测试）:
#   curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh | bash
#
# 安全说明：
# - 生产环境请使用 git clone 方式
# - curl 管道执行无法验证脚本完整性
# - 建议先下载脚本审查后再执行

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 Aevia - AI 虚拟伴侣 一键安装"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. 检查 OpenClaw 环境
echo "📋 检查 OpenClaw 环境..."
OPENCLAW_SKILLS_DIR="$HOME/.openclaw/workspace/skills"

if [ ! -d "$OPENCLAW_SKILLS_DIR" ]; then
  echo "❌ 错误：未找到 OpenClaw skills 目录"
  echo "   路径：$OPENCLAW_SKILLS_DIR"
  echo ""
  echo "请先安装 OpenClaw: https://openclaw.ai"
  exit 1
fi

echo "✅ OpenClaw 环境存在"
echo ""

# 2. 克隆或更新项目
INSTALL_DIR="$OPENCLAW_SKILLS_DIR/xiaorou"

if [ -d "$INSTALL_DIR" ]; then
  echo "🔄 检测到已安装的小柔 AI，正在更新..."
  cd "$INSTALL_DIR"
  git pull origin main
else
  echo "📦 正在下载小柔 AI..."
  cd "$OPENCLAW_SKILLS_DIR"
  git clone https://github.com/OMclaw/xiaorou.git
  cd xiaorou
fi

echo ""

# 3. 运行安装脚本
echo "🚀 正在安装小柔 AI..."
echo ""

if [ -f "install.sh" ]; then
  bash install.sh
else
  echo "❌ 错误：未找到 install.sh"
  exit 1
fi

echo ""

# 4. 完成
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 小柔 AI 安装完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 下一步："
echo "  1. 重启 OpenClaw（如果正在运行）"
echo "  2. 对小柔说：'早安' 或 '发张自拍'"
echo "  3. 享受 AI 伴侣的陪伴～ 🦞❤️"
echo ""
echo "📚 更多帮助："
echo "  cd $INSTALL_DIR"
echo "  cat README.md"
echo ""
