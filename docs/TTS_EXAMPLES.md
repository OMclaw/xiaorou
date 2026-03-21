# TTS 使用示例

## 快速开始

### 1. 基础用法

```bash
# 最简单的方式（使用默认温柔女声）
python3 scripts/tts.py "你好，我是小柔" /tmp/voice.mp3

# 使用参数方式
python3 scripts/tts.py --text "早上好呀" --output /tmp/morning.mp3
```

### 2. 选择音色

```bash
# 温柔女声（默认）
python3 scripts/tts.py --text "你好" --voice longxiaochun --output /tmp/voice1.mp3

# 活泼女声
python3 scripts/tts.py --text "你好" --voice longxiaoman --output /tmp/voice2.mp3

# 知性女声
python3 scripts/tts.py --text "你好" --voice longxiaoxia --output /tmp/voice3.mp3

# 甜美女声
python3 scripts/tts.py --text "你好" --voice longxiaoyu --output /tmp/voice4.mp3

# 成熟女声
python3 scripts/tts.py --text "你好" --voice longxiaoyan --output /tmp/voice5.mp3
```

### 3. 调整语速

```bash
# 正常语速（默认 1.0）
python3 scripts/tts.py --text "你好" --speed 1.0 --output /tmp/normal.mp3

# 快速（1.5 倍）
python3 scripts/tts.py --text "你好" --speed 1.5 --output /tmp/fast.mp3

# 慢速（0.8 倍）
python3 scripts/tts.py --text "你好" --speed 0.8 --output /tmp/slow.mp3
```

### 4. 选择输出格式

```bash
# MP3 格式（默认，推荐）
python3 scripts/tts.py --text "你好" --format mp3 --output /tmp/voice.mp3

# WAV 格式（无损）
python3 scripts/tts.py --text "你好" --format wav --output /tmp/voice.wav

# PCM 格式（原始音频）
python3 scripts/tts.py --text "你好" --format pcm --output /tmp/voice.pcm
```

### 5. 在 aevia.sh 中使用

```bash
# 发送语音消息到飞书
bash scripts/aevia.sh "发语音：早上好呀，今天也要加油哦" feishu

# 发送语音消息到 Telegram
bash scripts/aevia.sh "语音消息：我想你了" telegram

# 说句话（不发送，仅生成）
bash scripts/aevia.sh "说句话：你好" 
```

## 触发词

在 `aevia.sh` 中，以下触发词会激活语音模式：

- `发语音` - 最常用
- `语音消息` - 明确指定
- `说句话` - 自然表达
- `语音回复` - 正式表达
- `voice` - 英文触发
- `tts` - 技术术语

示例：
```bash
bash scripts/aevia.sh "发语音：早安" feishu
bash scripts/aevia.sh "语音消息：记得吃早饭" feishu
bash scripts/aevia.sh "说句话：我好想你" feishu
```

## 编程调用

```python
from scripts.tts import text_to_speech, list_available_voices

# 查看可用音色
voices = list_available_voices()
print(f"可用音色：{voices}")

# 生成语音
success, message = text_to_speech(
    text="你好，我是小柔",
    output_path="/tmp/voice.mp3",
    voice="longxiaochun",  # 温柔女声
    model="cosyvoice-v3.5-plus",
    audio_format="mp3",
    speed=1.0,
    retries=3
)

if success:
    print(f"语音生成成功：{message}")
else:
    print(f"语音生成失败：{message}")
```

## 环境变量

```bash
# 设置 API Key（必需）
export DASHSCOPE_API_KEY="sk-your-api-key"

# 可选：自定义角色名称
export AEVIA_CHARACTER_NAME="小柔"
```

## 常见问题

### Q: 语音生成失败？
A: 检查以下几点：
1. API Key 是否正确设置
2. 网络连接是否正常
3. 文本是否过长（限制 500 字）
4. 查看日志获取详细错误信息

### Q: 如何调整音量？
A: 当前 API 不支持直接调整音量，建议在播放端调整。

### Q: 支持长文本吗？
A: 单次请求最多 500 字。如需更长文本，建议分段生成后合并。

### Q: 生成的语音文件在哪里？
A: 在你指定的输出路径。如果未指定，需要手动提供路径。

### Q: 临时文件会自动清理吗？
A: 是的，脚本会自动清理临时文件。但如果程序异常退出，可能需要手动清理 `/tmp` 目录。

## 性能优化

### 批量生成

```bash
#!/bin/bash
# 批量生成语音示例

texts=(
  "早上好呀"
  "中午好"
  "晚上好"
  "晚安"
)

for i in "${!texts[@]}"; do
  python3 scripts/tts.py "${texts[$i]}" "/tmp/greeting_$i.mp3"
done
```

### 缓存常用语音

对于常用的问候语，可以预先生成并缓存：

```bash
# 预先生成
python3 scripts/tts.py "早上好呀" ~/.xiaorou/cache/morning.mp3
python3 scripts/tts.py "晚安" ~/.xiaorou/cache/night.mp3

# 使用时直接播放
```

## 技术细节

- **模型**: CosyVoice-v3.5-plus
- **采样率**: 24000 Hz
- **比特率**: 128 kbps (MP3)
- **延迟**: 通常 2-5 秒（取决于文本长度）
- **并发**: 建议单次请求，避免并发限制

## 最佳实践

1. ✅ 使用简短清晰的文本（<200 字）
2. ✅ 选择合适的音色（温柔女声最自然）
3. ✅ 语速保持在 0.8-1.2 之间
4. ✅ 使用 MP3 格式（兼容性好）
5. ✅ 添加错误处理和重试机制
6. ✅ 及时清理临时文件

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
