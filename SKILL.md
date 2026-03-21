---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、角色定制、语音消息
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write WebFetch Bash(npm:*) Bash(python3:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🎙️ **语音消息** - CosyVoice-v3-flash 高质量 TTS
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

# 🎙️ 语音消息
bash scripts/aevia.sh "发语音：早上好呀" feishu
bash scripts/aevia.sh "语音消息：今天也要加油哦" feishu

# 角色
bash scripts/character.sh "一个温柔可爱的女孩"
```

## 配置

自动从 `~/.openclaw/openclaw.json` 读取 API Key。

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

## 🎙️ TTS 语音

**引擎**: 阿里云 CosyVoice-v3-flash

**默认音色**: `longqiang_v3` (成熟男声)

**可用音色**:
- `longqiang_v3` - 成熟男声（默认）⭐
- `longxiaochun_v2` - 温柔女声
- `longxiaoman_v2` - 活泼女声
- `longxiaoxia_v2` - 知性女声
- `longxiaoyu_v2` - 甜美女声
- `longxiaoyan_v2` - 成熟女声
- `longanyang` - 阳光男声

**使用示例**:
```bash
# 使用默认音色
python3 scripts/tts.py "你好" /tmp/voice.mp3

# 指定音色
python3 scripts/tts.py "你好" /tmp/voice.mp3 longxiaochun_v2

# Shell 脚本
bash scripts/tts.sh "你好，我是小柔" /tmp/voice.mp3 longqiang_v3
```

## API

- 聊天：Qwen3.5-plus
- 自拍：Wan2.6-image
- 头像：Z-image-turbo
- 语音：CosyVoice-v3-flash（音色：longqiang_v3 等）

## 更多

查看 README.md 获取完整文档。
