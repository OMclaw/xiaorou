---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、视频生成、角色定制、语音消息
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write Bash(python3:*) Bash(ffmpeg:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus
- 📸 **自拍生成** - Wan2.6-image / qwen-image-2.0-pro
- 🔄 **换脸生成** - 4 模型并发（wan2.7-image / wan2.7-image-pro / qwen-image-2.0 / qwen-image-2.0-pro）
- 🎬 **视频生成** - wan2.6-i2v（图片 + 文字 → 视频）
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

# 换脸（4 模型并发）
python3 scripts/face_swap.py /path/to/image.jpg
python3 scripts/face_swap.py /path/to/image.jpg --image2 /path/to/target.jpg
python3 scripts/face_swap.py /path/to/image.jpg --models wan2.7-image qwen-image-2.0

# 视频生成（单步）
python3 scripts/video_generator.py --img photo.jpg --prompt "一个女孩在海边散步" --output video.mp4

# 视频生成（完整流程：图片 + 语音→视频）
python3 scripts/video_pipeline.py \
  --reference photo.jpg \
  --scene-prompt "一个美丽的女孩在海边微笑" \
  --tts-text "你好呀，今天天气真好～" \
  --video-prompt "一个女孩在海边微笑，微风吹拂头发，阳光明媚" \
  --duration 5 \
  --target "user:ou_xxx"

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

## 换脸模式

**使用方式**：用户发送一张图片 + 说"换脸"

**生成流程**：
1. 使用用户提供的图片作为图 1
2. 使用小柔默认头像（assets/default-character.png）作为图 2
3. 4 个模型并发生成（wan2.7-image / wan2.7-image-pro / qwen-image-2.0 / qwen-image-2.0-pro）
4. 统一 Prompt：「我想让图 1 的脸换成图 2 的脸部特征，其他图 1 的部分全部不变，最后要自然、无 AI 感、去掉水印」
5. 输出 4 张生成的图片

**命令行用法**：
```bash
# 使用默认小柔头像换脸
python3 scripts/face_swap.py /path/to/image.jpg

# 指定目标头像
python3 scripts/face_swap.py /path/to/image.jpg --image2 /path/to/target.jpg

# 指定使用的模型
python3 scripts/face_swap.py /path/to/image.jpg --models wan2.7-image qwen-image-2.0

# 详细输出
python3 scripts/face_swap.py /path/to/image.jpg --verbose
```

**输出位置**：`/tmp/openclaw/face_swaps/face_swap_<timestamp>/`

## API

- 聊天：Qwen3.5-plus
- 自拍：Wan2.6-image / qwen-image-2.0-pro
- 视频：wan2.6-i2v
- 头像：Z-image-turbo
- 语音：CosyVoice-v3-flash（默认：longyingxiao_v3）

**语音特性：**
- 飞书：OPUS 格式（语音气泡）
- 其他：MP3 格式
- 首包延迟：~1.6 秒

## 视频生成 API

**模型**：wan2.6-i2v

**支持模式**：
- 图片 + 文字 → 视频
- 纯文字 → 视频
- 图片 + 文字 + 音频 → 视频（带音频）

**参数**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| resolution | 分辨率 | 720P |
| duration | 视频时长 | 10 秒 |
| audio | 是否启用音频 | false |
| shot_type | 镜头类型 | multi |
| prompt_extend | 是否扩展提示词 | true |

**生成时间**：约 3-10 分钟（异步任务）

**输出格式**：MP4

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
