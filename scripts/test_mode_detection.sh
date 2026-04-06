#!/bin/bash
# test_mode_detection.sh
set -euo pipefail  # 测试三种生图模式的指令识别

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 模拟 detect_mode 函数（从 aevia.sh 复制）
detect_mode() {
  local input="$1"
  local has_image="${AEVIA_IMAGE_PATH:-}"
  
  # 语音模式（最高优先级）
  if printf '%s' "$input" | grep -qiE "发语音|语音消息|说句话|tts"; then
    echo "voice"
    return
  fi
  
  # 视频模式（第二优先级，检查完整关键词 + 截断保护）
  if printf '%s' "$input" | grep -qiE "生成视频|做视频|图生视频|视频生成"; then
    echo "video"
    return
  fi
  
  # ========== 参考生图模式 ==========
  # 关键词：参考、模仿、照[著着]、学这张、生成一张类似的、同样的场景
  # 条件：必须有图片 + 参考类关键词
  if [ -n "$has_image" ]; then
    if printf '%s' "$input" | grep -qiE "参考|模仿|照[著着]|学这张|类似的|同样的|照这个|按这个|生成一张|来一张"; then
      echo "selfie-reference"
      return
    fi
  fi
  
  # ========== 场景生图模式 ==========
  # 关键词：照片、图片、自拍、发张、看看你、穿、穿搭、生成、来一张、想要、场景、在...里/前/下
  # 条件：有场景描述（可以是纯文字，也可以有图片但没参考关键词）
  if printf '%s' "$input" | grep -qiE "照片|图片|自拍|发张|看看你|穿|穿搭|生成|来一张|想要|场景|在.*里|在.*前|在.*下"; then
    if [ -n "$has_image" ]; then
      # 有图片但没参考关键词 → 使用图片作为场景参考（参考生图的简化版）
      echo "selfie-reference"
    else
      # 纯文字场景描述 → 场景生图
      echo "selfie-scene"
    fi
    return
  fi
  
  # 默认：聊天模式
  echo "chat"
}

# 测试函数
run_test() {
  local input="$1"
  local image="$2"
  local expected="$3"
  
  local result
  result=$(AEVIA_IMAGE_PATH="$image" detect_mode "$input" 2>&1)
  
  if [ "$result" = "$expected" ]; then
    echo "✅ PASS: '$input' [图:$([ -n "$image" ] && echo "有" || echo "无")] → $result"
    return 0
  else
    echo "❌ FAIL: '$input' [图:$([ -n "$image" ] && echo "有" || echo "无")]"
    echo "   期望：$expected"
    echo "   实际：$result"
    return 1
  fi
}

echo "======================================"
echo "🧪 三种生图模式指令识别测试"
echo "======================================"
echo ""

passed=0
failed=0

# 场景生图（无图）
if run_test "发张自拍，在海边看日落" "" "selfie-scene"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "想要一张在咖啡厅看书的照片" "" "selfie-scene"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "生成一张在樱花树下的场景" "" "selfie-scene"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "来一张穿汉服在古城的照片" "" "selfie-scene"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "自拍一张，穿白色连衣裙" "" "selfie-scene"; then passed=$((passed+1)); else failed=$((failed+1)); fi

# 参考生图（有图）
if run_test "参考这张图生成一张" "/tmp/test.jpg" "selfie-reference"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "模仿这个场景来一张" "/tmp/test.jpg" "selfie-reference"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "照这个样子生成" "/tmp/test.jpg" "selfie-reference"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "生成一张类似的" "/tmp/test.jpg" "selfie-reference"; then passed=$((passed+1)); else failed=$((failed+1)); fi

# 聊天模式
if run_test "早安" "" "chat"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "你好呀" "" "chat"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "今天天气怎么样" "" "chat"; then passed=$((passed+1)); else failed=$((failed+1)); fi

# 语音模式
if run_test "发语音：早上好呀" "" "voice"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "语音消息：想你" "" "voice"; then passed=$((passed+1)); else failed=$((failed+1)); fi

# 视频模式
if run_test "生成视频，在海边散步" "" "video"; then passed=$((passed+1)); else failed=$((failed+1)); fi
if run_test "做视频，用这张图" "" "video"; then passed=$((passed+1)); else failed=$((failed+1)); fi

echo ""
echo "======================================"
echo "📊 测试结果：$passed 通过，$failed 失败"
echo "======================================"

[ $failed -eq 0 ] && exit 0 || exit 1
