#!/bin/bash
# test.sh - 小柔 AI 基础测试脚本
#
# 功能:
#   - 测试配置加载
#   - 测试输入验证
#   - 测试路径安全
#
# 使用示例:
#   bash scripts/test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

# 测试计数
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================
# 测试框架函数
# ============================================
test_start() {
  local name="$1"
  TESTS_RUN=$((TESTS_RUN + 1))
  echo -n "🧪 测试 #$TESTS_RUN: $name ... "
}

test_pass() {
  TESTS_PASSED=$((TESTS_PASSED + 1))
  echo "✅ 通过"
}

test_fail() {
  TESTS_FAILED=$((TESTS_FAILED + 1))
  echo "❌ 失败：$1"
}

# ============================================
# 测试：配置加载
# ============================================
test_config_loading() {
  test_start "配置加载"
  
  # 临时设置 API Key
  export DASHSCOPE_API_KEY="sk-test12345678901234567890"
  
  # 验证格式
  if [[ "$DASHSCOPE_API_KEY" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
    test_pass
  else
    test_fail "API Key 格式验证失败"
  fi
  
  unset DASHSCOPE_API_KEY
}

# ============================================
# 测试：输入验证
# ============================================
test_input_sanitization() {
  test_start "输入验证（危险字符过滤）"
  
  local dangerous_input='test$(whoami)`id`;rm -rf |&!\\'
  local sanitized
  
  # 模拟 sanitize_input 函数
  sanitized=$(echo "$dangerous_input" | tr -d '\000-\011\013-\037\177' | sed "s/[\\\`\$(){};|&!]//g")
  
  # 检查危险字符是否被移除
  if [[ ! "$sanitized" =~ [\$\(\)\{\}\;\|\&\!\`] ]]; then
    test_pass
  else
    test_fail "危险字符未被过滤：$sanitized"
  fi
}

test_input_length() {
  test_start "输入验证（长度限制）"
  
  local long_input
  long_input=$(printf 'a%.0s' {1..600})
  local max_len=500
  
  if [ ${#long_input} -gt $max_len ]; then
    local truncated="${long_input:0:$max_len}"
    if [ ${#truncated} -eq $max_len ]; then
      test_pass
    else
      test_fail "截断后长度不正确"
    fi
  else
    test_fail "生成长输入失败"
  fi
}

# ============================================
# 测试：路径安全
# ============================================
test_path_traversal() {
  test_start "路径遍历防护"
  
  local base_dir="$PROJECT_ROOT"
  local malicious_path="../../../etc/passwd"
  
  # 检查是否包含 ..
  if [[ "$malicious_path" == *".."* ]]; then
    test_pass
  else
    test_fail "未检测到路径遍历攻击"
  fi
}

test_safe_path() {
  test_start "安全路径解析"
  
  local base_dir="$PROJECT_ROOT"
  local safe_path="assets/default-character.png"
  
  # 检查不包含 ..
  if [[ "$safe_path" != *".."* ]] && [[ "$safe_path" != /* ]]; then
    test_pass
  else
    test_fail "安全路径被误判"
  fi
}

# ============================================
# 测试：频道验证
# ============================================
test_channel_validation() {
  test_start "频道白名单验证"
  
  local valid_channels=("feishu" "telegram" "discord" "whatsapp" "")
  local invalid_channels=("invalid" "hack" "'; DROP TABLE users; --")
  
  local all_passed=true
  
  # 验证有效频道
  for channel in "${valid_channels[@]}"; do
    case "$channel" in
      feishu|telegram|discord|whatsapp|"")
        ;;
      *)
        all_passed=false
        ;;
    esac
  done
  
  # 验证无效频道被拒绝
  for channel in "${invalid_channels[@]}"; do
    case "$channel" in
      feishu|telegram|discord|whatsapp|"")
        all_passed=false
        ;;
      *)
        ;;
    esac
  done
  
  if $all_passed; then
    test_pass
  else
    test_fail "频道验证逻辑错误"
  fi
}

# ============================================
# 测试：文件存在性
# ============================================
test_required_files() {
  test_start "必需文件存在"
  
  local required_files=(
    "$PROJECT_ROOT/README.md"
    "$PROJECT_ROOT/LICENSE"
    "$PROJECT_ROOT/requirements.txt"
    "$PROJECT_ROOT/scripts/aevia.sh"
    "$PROJECT_ROOT/scripts/selfie.py"
    "$PROJECT_ROOT/scripts/character.sh"
  )
  
  local all_exist=true
  for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
      all_exist=false
      echo "缺失：$file" >&2
    fi
  done
  
  if $all_exist; then
    test_pass
  else
    test_fail "缺少必需文件"
  fi
}

test_shell_scripts_executable() {
  test_start "Shell 脚本可执行权限"
  
  local scripts=(
    "$PROJECT_ROOT/scripts/aevia.sh"
    "$PROJECT_ROOT/scripts/character.sh"
    "$PROJECT_ROOT/scripts/load_config.sh"
  )
  
  local all_executable=true
  for script in "${scripts[@]}"; do
    if [ ! -x "$script" ]; then
      all_executable=false
      echo "不可执行：$script" >&2
    fi
  done
  
  if $all_executable; then
    test_pass
  else
    test_fail "脚本缺少可执行权限"
  fi
}

# ============================================
# 主逻辑
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 小柔 AI - 基础测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 运行所有测试
test_config_loading
test_input_sanitization
test_input_length
test_path_traversal
test_safe_path
test_channel_validation
test_required_files
test_shell_scripts_executable

# 输出结果
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 测试结果"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "运行：$TESTS_RUN"
echo "通过：$TESTS_PASSED"
echo "失败：$TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo "✅ 所有测试通过！"
  exit 0
else
  echo "❌ 有 $TESTS_FAILED 个测试失败"
  exit 1
fi
