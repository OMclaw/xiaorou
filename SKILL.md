---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、角色定制、语音消息（飞书语音气泡）
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write WebFetch Bash(npm:*) Bash(python3:*) Bash(ffmpeg:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🎙️ **语音消息** - CosyVoice-v3-flash 温柔女声 TTS（飞书显示语音气泡）
- 🌐 **多平台** - 飞书/Telegram/Discord/WhatsApp

## 安装

```bash
curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh | bash
```

## 使用

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 自拍
bash scripts/aevia.sh "发张自拍" feishu

# 🎙️ 语音消息（飞书显示语音气泡）
bash scripts/aevia.sh "发语音：早上好呀" feishu
bash scripts/aevia.sh "语音消息：今天也要加油哦" feishu
bash scripts/aevia.sh "说句话：我想你了" feishu

# 角色
bash scripts/character.sh "一个温柔可爱的女孩"
```

## 配置

**依赖安装：**
```bash
# Python 3.9
brew install python@3.9

# dashscope SDK
/home/linuxbrew/.linuxbrew/bin/python3.9 -m pip install dashscope

# ffmpeg（音频转换）
brew install ffmpeg
```

**API Key 配置：**
自动从 `~/.openclaw/openclaw.json` 读取，无需手动设置。

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
- 语音：CosyVoice-v3-flash（音色：longyingxiao_v3 等，默认：longyingxiao_v3）

**语音特性：**
- 飞书：OPUS 格式（显示语音气泡，可点击播放）
- 其他平台：MP3 格式
- 首包延迟：约 1.6 秒
- 输出质量：32kbps, 24kHz

## 更多

查看 README.md 获取完整文档。
