#!/bin/bash
# install.sh - 小柔 AI 安装脚本
#
# 功能:
#   - 检查 OpenClaw 配置
#   - 同步角色身份文件（SOUL.md, IDENTITY.md）
#   - 备份用户现有配置
#   - 询问是否覆盖现有文件
#
# 使用示例:
#   bash install.sh
#   AEVIA_CHARACTER_NAME="小柔" bash install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${SCRIPT_DIR}/../.."

# ============================================
# 统一错误处理函数
# ============================================
error() {
  echo "❌ 错误：$*" >&2
  exit 1
}

warn() {
  echo "⚠️ 警告：$*" >&2
}

info() {
  echo "ℹ️  $*"
}

# ============================================
# 备份函数
# ============================================
backup_file() {
  local file="$1"
  if [ -f "$file" ]; then
    local backup="${file}.backup.$(date +%Y%m%d%H%M%S)"
    cp "$file" "$backup"
    info "📦 已备份：$backup"
    return 0
  fi
  return 1
}

# ============================================
# 询问是否覆盖
# ============================================
ask_overwrite() {
  local file="$1"
  local response
  
  # 非交互模式下默认不覆盖
  if [ ! -t 0 ]; then
    warn "$file 已存在，非交互模式下跳过"
    return 1
  fi
  
  read -p "⚠️  $file 已存在，是否覆盖？[y/N] " response
  case "$response" in
    [yY][eE][sS]|[yY])
      return 0
      ;;
    *)
      info "⏭️  跳过 $file"
      return 1
      ;;
  esac
}

# ============================================
# 主逻辑
# ============================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🦞 小柔 AI - 安装程序"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查 OpenClaw 配置
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
if [ ! -f "$OPENCLAW_CONFIG" ]; then
  error "未找到 OpenClaw 配置文件：$OPENCLAW_CONFIG"
fi
info "✅ OpenClaw 配置存在"

# 同步身份文件
SOUL_FILE="$WORKSPACE_DIR/SOUL.md"
IDENTITY_FILE="$WORKSPACE_DIR/IDENTITY.md"
TARGET_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

# 处理 SOUL.md
if [ -f "$SOUL_FILE" ]; then
  if ask_overwrite "$SOUL_FILE"; then
    backup_file "$SOUL_FILE"
    info "📝 更新 SOUL.md..."
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
    info "✅ SOUL.md 已更新"
  fi
else
  info "📝 创建 SOUL.md..."
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
  info "✅ SOUL.md 已创建"
fi

# 处理 IDENTITY.md
if [ -f "$IDENTITY_FILE" ]; then
  if ask_overwrite "$IDENTITY_FILE"; then
    backup_file "$IDENTITY_FILE"
    info "📝 更新 IDENTITY.md..."
    cat > "$IDENTITY_FILE" <<EOF
# IDENTITY.md

- **Name:** ${TARGET_NAME}
- **Creature:** AI Virtual Companion
- **Vibe:** Warm, caring, playful
- **Emoji:** 🦞
EOF
    info "✅ IDENTITY.md 已更新"
  fi
else
  info "📝 创建 IDENTITY.md..."
  cat > "$IDENTITY_FILE" <<EOF
# IDENTITY.md

- **Name:** ${TARGET_NAME}
- **Creature:** AI Virtual Companion
- **Vibe:** Warm, caring, playful
- **Emoji:** 🦞
EOF
  info "✅ IDENTITY.md 已创建"
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
echo ""
