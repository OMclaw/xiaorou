#!/bin/bash
# sync_identity.sh - 同步 Aevia 角色名到 OpenClaw 身份文件
# 使用方法：bash scripts/sync_identity.sh [角色名]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${SCRIPT_DIR}/../.."

# 角色名优先级：命令行参数 > 环境变量 > 默认值
CHARACTER_NAME="${1:-${AEVIA_CHARACTER_NAME:-小柔}}"

# 验证角色名：不能为空，使用白名单验证防止注入
if [ -z "$CHARACTER_NAME" ]; then
  echo "❌ Error: Character name cannot be empty"
  exit 1
fi

# 白名单验证：只允许中文、字母、数字、下划线和连字符
if [[ ! "$CHARACTER_NAME" =~ ^[a-zA-Z0-9\u4e00-\u9fa5_-]+$ ]]; then
  echo "❌ Error: Invalid character name format. Only letters, numbers, Chinese characters, underscores and hyphens are allowed."
  exit 1
fi

# 使用 jq 进行安全的字符串转义（防止 sed 注入）
if command -v jq &> /dev/null; then
  CHARACTER_NAME_ESCAPED=$(printf '%s' "$CHARACTER_NAME" | jq -Rs '.')
else
  # 降级方案：转义所有特殊字符
  CHARACTER_NAME_ESCAPED=$(printf '%s\n' "$CHARACTER_NAME" | sed 's/[]\/$*.^[]/\\&/g')
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Aevia Identity Sync"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Target workspace: $WORKSPACE_DIR"
echo "Character name: $CHARACTER_NAME"
echo ""

# 检查文件是否存在
SOUL_FILE="$WORKSPACE_DIR/SOUL.md"
IDENTITY_FILE="$WORKSPACE_DIR/IDENTITY.md"

if [ ! -f "$SOUL_FILE" ]; then
  echo "❌ Error: SOUL.md not found at $SOUL_FILE"
  exit 1
fi

if [ ! -f "$IDENTITY_FILE" ]; then
  echo "❌ Error: IDENTITY.md not found at $IDENTITY_FILE"
  exit 1
fi

# 备份原文件（使用纳秒时间戳避免冲突）
echo "📦 Creating backups..."
cp "$SOUL_FILE" "${SOUL_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
cp "$IDENTITY_FILE" "${IDENTITY_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
echo "✅ Backups created"
echo ""

# 更新 SOUL.md（使用转义后的变量）
echo "📝 Updating SOUL.md..."
if grep -q "^\*\*中文名\*\*:" "$SOUL_FILE" 2>/dev/null; then
  sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$SOUL_FILE"
else
  sed -i "s/^\*\*Name\*\*: .*/\*\*Name\*\*: $CHARACTER_NAME_ESCAPED\n- \*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$SOUL_FILE"
fi
echo "✅ SOUL.md updated"

# 更新 IDENTITY.md（使用转义后的变量）
echo "📝 Updating IDENTITY.md..."
if grep -q "^\*\*Name:\*\*" "$IDENTITY_FILE" 2>/dev/null; then
  sed -i "s/^\*\*Name:\*\* .*/\*\*Name:\*\* $CHARACTER_NAME_ESCAPED/" "$IDENTITY_FILE"
fi

if grep -q "^\*\*中文名\*\*:" "$IDENTITY_FILE" 2>/dev/null; then
  sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$IDENTITY_FILE"
else
  sed -i "/^\*\*Name:\*\*/a - \*\*中文名\*\*: $CHARACTER_NAME_ESCAPED" "$IDENTITY_FILE"
fi
echo "✅ IDENTITY.md updated"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Sync completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Changes made:"
echo "  - SOUL.md: Name updated to '$CHARACTER_NAME'"
echo "  - IDENTITY.md: Name updated to '$CHARACTER_NAME'"
echo ""
echo "⚠️  Note: A new session may be required for changes to take effect."
echo ""

# 显示变更
echo "📋 Preview changes:"
echo "────────────────────────────────"
echo "SOUL.md:"
grep -E "^\*\*(中文)?Name\*\*:" "$SOUL_FILE" | head -3
echo ""
echo "IDENTITY.md:"
grep -E "^\*\*(中文)?Name:\*\*" "$IDENTITY_FILE" | head -3
echo "────────────────────────────────"
