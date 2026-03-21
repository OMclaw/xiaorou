#!/bin/bash
# tts.sh - 使用阿里云 CosyVoice 生成语音
#
# 使用示例:
#   bash scripts/tts.sh "你好，我是小柔" /tmp/voice.mp3
#   bash scripts/tts.sh "早上好" /tmp/morning.mp3 longqiang_v3

set -euo pipefail

TEXT="${1:-你好，我是小柔}"
OUTPUT="${2:-/tmp/voice.mp3}"
VOICE="${3:-longqiang_v3}"
MODEL="${4:-cosyvoice-v3-flash}"

echo "🎙️ TTS 生成中 (CosyVoice)..." >&2
echo "📝 文本：$TEXT" >&2
echo "🎵 音色：$VOICE" >&2
echo "🤖 模型：$MODEL" >&2

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 创建输出目录
mkdir -p "$(dirname "$OUTPUT")"

# 检查 API Key
if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
    # 尝试从 OpenClaw 配置读取
    CONFIG_FILE="$HOME/.openclaw/openclaw.json"
    if [ -f "$CONFIG_FILE" ]; then
        export DASHSCOPE_API_KEY=$(python3 -c "
import json
import sys
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    for ext in config.get('extensions', {}).values():
        if isinstance(ext, dict):
            env = ext.get('env', {})
            if 'DASHSCOPE_API_KEY' in env:
                print(env['DASHSCOPE_API_KEY'])
                sys.exit(0)
except:
    pass
sys.exit(1)
" 2>/dev/null || echo "")
    fi
fi

if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
    echo "❌ 错误：未设置 DASHSCOPE_API_KEY" >&2
    echo "   请设置环境变量或配置 ~/.openclaw/openclaw.json" >&2
    exit 1
fi

# 使用 Python 脚本生成
python3 "$SCRIPT_DIR/tts.py" \
    --text "$TEXT" \
    --output "$OUTPUT" \
    --voice "$VOICE" \
    --model "$MODEL"

if [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    echo "✅ 生成成功：$OUTPUT ($(stat -c%s "$OUTPUT") bytes)" >&2
    exit 0
else
    echo "❌ TTS 生成失败" >&2
    exit 1
fi
