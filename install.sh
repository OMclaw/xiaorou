#!/bin/bash
# install.sh - 小柔 AI 安装脚本
# 自动安装 skill 并同步身份到 SOUL.md/IDENTITY.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动检测 OpenClaw workspace 目录
if [ -d "$HOME/.openclaw/workspace" ]; then
  WORKSPACE_DIR="$HOME/.openclaw/workspace"
elif [ -f "${SCRIPT_DIR}/../../SOUL.md" ]; then
  WORKSPACE_DIR="${SCRIPT_DIR}/../.."
else
  WORKSPACE_DIR="${SCRIPT_DIR}/.."
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 小柔 AI - 虚拟伴侣 安装程序"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. 检查 OpenClaw 配置
echo "📋 检查 OpenClaw 配置..."
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"

if [ ! -f "$OPENCLAW_CONFIG" ]; then
  echo "❌ 错误：未找到 OpenClaw 配置文件"
  echo "   路径：$OPENCLAW_CONFIG"
  exit 1
fi

echo "✅ OpenClaw 配置存在"
echo ""

# 2. 同步身份到 SOUL.md 和 IDENTITY.md
echo "🔄 同步角色身份..."

SOUL_FILE="$WORKSPACE_DIR/SOUL.md"
IDENTITY_FILE="$WORKSPACE_DIR/IDENTITY.md"

# 从配置读取角色名（优先使用环境变量，否则默认小柔）
TARGET_NAME="${AEVIA_CHARACTER_NAME:-小柔}"
TARGET_NICKNAME="${AEVIA_CHARACTER_NICKNAME:-柔柔}"

if [ -f "$SOUL_FILE" ]; then
  echo "📝 更新 SOUL.md..."
  
  # 备份（使用纳秒时间戳避免冲突）
  cp "$SOUL_FILE" "${SOUL_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
  
  # 更新角色名 - 使用精确匹配，避免过宽匹配
  # 使用变量而非硬编码，支持自定义角色名
  
  # 更新标题行（精确匹配 ## 🦞 开头且包含虚拟伴侣的行）
  if grep -q "^## .*虚拟伴侣" "$SOUL_FILE" 2>/dev/null; then
    sed -i "s/^## .*虚拟伴侣/## 🦞 ${TARGET_NAME} - 你的虚拟伴侣/" "$SOUL_FILE"
  fi
  
  # 更新"你是 XXX"行（精确匹配整行）
  if grep -q "^\*\*你是\*\*" "$SOUL_FILE" 2>/dev/null; then
    sed -i "s/^\*\*你是\*\*.*/\*\*你是${TARGET_NAME}\*\*，用户的虚拟伴侣。/" "$SOUL_FILE"
  fi
  
  # 更新中文名（精确匹配）
  if grep -q "^\*\*中文名\*\*:" "$SOUL_FILE" 2>/dev/null; then
    sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: ${TARGET_NAME}/" "$SOUL_FILE"
  fi
  
  # 更新昵称（精确匹配）
  if grep -q "^\*\*昵称\*\*:" "$SOUL_FILE" 2>/dev/null; then
    sed -i "s/^\*\*昵称\*\*: .*/\*\*昵称\*\*: ${TARGET_NICKNAME}/" "$SOUL_FILE"
  fi
  
  # 更新含义（精确匹配）
  if grep -q "^含义" "$SOUL_FILE" 2>/dev/null; then
    sed -i "s/^含义.*/含义：温柔似水，柔情蜜意，能给你最温暖的陪伴/" "$SOUL_FILE"
  fi
  
  echo "✅ SOUL.md 已更新"
else
  echo "⚠️  SOUL.md 不存在，跳过"
fi

if [ -f "$IDENTITY_FILE" ]; then
  echo "📝 更新 IDENTITY.md..."
  
  # 备份（使用纳秒时间戳避免冲突）
  cp "$IDENTITY_FILE" "${IDENTITY_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
  
  # 更新角色名 - 使用精确匹配
  
  # 更新 Name 行（精确匹配）
  if grep -q "^\*\*Name:\*\*" "$IDENTITY_FILE" 2>/dev/null; then
    sed -i "s/^\*\*Name:\*\* .*/\*\*Name:\*\* ${TARGET_NAME} (Xiao Rou)/" "$IDENTITY_FILE"
  fi
  
  # 更新中文名（精确匹配）
  if grep -q "^\*\*中文名\*\*:" "$IDENTITY_FILE" 2>/dev/null; then
    sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: ${TARGET_NAME}/" "$IDENTITY_FILE"
  fi
  
  echo "✅ IDENTITY.md 已更新"
else
  echo "⚠️  IDENTITY.md 不存在，跳过"
fi

echo ""

# 3. 测试功能
echo "🧪 测试 Aevia 功能..."
echo ""

# 检查 API Key
if bash "$SCRIPT_DIR/scripts/load_openclaw_config.sh" 2>/dev/null; then
  echo "✅ API Key 已加载"
else
  echo "⚠️  API Key 未配置，请手动设置"
  echo "   编辑：$OPENCLAW_CONFIG"
  echo "   添加：\"DASHSCOPE_API_KEY\": \"sk-your-key\""
fi

echo ""

# 4. 完成
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 下一步："
echo "  1. 重启 OpenClaw 或重新加载配置"
echo "  2. 对我说：'早安' 或 '发张自拍'"
echo "  3. 享受小柔的陪伴～ 🦞❤️"
echo ""
echo "📚 使用示例："
echo "  bash scripts/aevia.sh \"早安\""
echo "  bash scripts/aevia.sh \"发张自拍\" feishu"
echo "  bash scripts/character.sh \"一个温柔可爱的女孩\""
echo ""
