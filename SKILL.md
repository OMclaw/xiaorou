---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、角色定制、语音消息
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write Bash(python3:*) Bash(ffmpeg:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus
- 📸 **自拍生成** - Wan2.6-image
- 🎨 **角色定制** - Z-image
- 🎙️ **语音消息** - CosyVoice-v3-flash（飞书语音气泡）
- 🌐 **多平台** - 飞书/Telegram/Discord/WhatsApp

## 安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git
cd xiaorou && bash install.sh
```

## 使用

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 自拍
bash scripts/aevia.sh "发张自拍" feishu

# 语音
bash scripts/aevia.sh "发语音：早上好呀" feishu

# 角色
bash scripts/character.sh "一个温柔可爱的女孩"
```

## 配置

**依赖：**
```bash
brew install python@3.9 ffmpeg
/home/linuxbrew/.linuxbrew/bin/python3.9 -m pip install dashscope
```

**API Key：** 自动从 `~/.openclaw/openclaw.json` 读取。

或手动设置：
```bash
export DASHSCOPE_API_KEY="sk-xxx"
export AEVIA_CHARACTER_NAME="小柔"
```

## 自拍模式

| 模式 | 关键词 | 场景 |
|------|--------|------|
| mirror | 穿、衣服、穿搭、全身 | 对镜自拍 |
| direct | 咖啡厅、餐厅、特写 | 直接自拍 |
| auto | 其他 | 自动判断 |

## API

- 聊天：Qwen3.5-plus
- 自拍：Wan2.6-image
- 头像：Z-image-turbo
- 语音：CosyVoice-v3-flash（默认：longyingxiao_v3）

**语音特性：**
- 飞书：OPUS 格式（语音气泡）
- 其他：MP3 格式
- 首包延迟：~1.6 秒

## TTS 高级用法

```bash
# 直接使用
python3 scripts/tts.py "你好" /tmp/voice.mp3

# 选择音色
python3 scripts/tts.py --voice longxiaoxia --text "你好" --output /tmp/voice.mp3

# 列出音色
python3 scripts/tts.py --list-voices
```

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
