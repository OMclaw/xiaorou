#!/bin/bash
# tts.sh - 使用 Edge TTS 生成语音
#
# 使用示例:
#   bash scripts/tts.sh "你好，我是小柔" /tmp/voice.mp3
#   bash scripts/tts.sh "早上好" /tmp/morning.mp3 zh-CN-XiaoxiaoNeural

set -euo pipefail

TEXT="${1:-你好，我是小柔}"
OUTPUT="${2:-/tmp/voice.mp3}"
VOICE="${3:-zh-CN-XiaoxiaoNeural}"
RATE="${4:-+0%}"
VOLUME="${5:-+0%}"
PITCH="${6:-+0Hz}"

echo "🎙️ TTS 生成中..." >&2
echo "📝 文本：$TEXT" >&2
echo "🎵 音色：$VOICE" >&2

# 创建输出目录
mkdir -p "$(dirname "$OUTPUT")"

# 使用 edge-tts Python 模块（如果可用）
if python3 -c "import edge_tts" 2>/dev/null; then
    echo "使用 edge-tts Python 模块" >&2
    python3 -c "
import asyncio
import edge_tts

async def generate():
    communicate = edge_tts.Communicate('$TEXT', '$VOICE', rate='$RATE', volume='$VOLUME', pitch='$PITCH')
    await communicate.save('$OUTPUT')

asyncio.get_event_loop().run_until_complete(generate())
" 2>&1
    
    if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
        echo "✅ 生成成功：$OUTPUT ($(stat -c%s "$OUTPUT") bytes)" >&2
        exit 0
    fi
fi

# 备用方案：使用 curl 调用 Edge TTS 服务
echo "使用 curl 调用 Edge TTS 服务" >&2

# Edge TTS 使用 WebSocket，需要特殊处理
# 这里使用简化方案：调用在线 TTS 服务

# 使用 Google TTS（备用）
GOOGLE_TTS_URL="https://translate.google.com/translate_tts"

curl -s -A "Mozilla/5.0" -G "$GOOGLE_TTS_URL" \
    --data-urlencode "q=$TEXT" \
    --data-urlencode "tl=zh-CN" \
    --data-urlencode "client=tw-ob" \
    -o "$OUTPUT"

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    echo "✅ 生成成功：$OUTPUT ($(stat -c%s "$OUTPUT") bytes)" >&2
    exit 0
else
    echo "❌ TTS 生成失败" >&2
    exit 1
fi
