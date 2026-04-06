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

### 💬 基础用法

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 语音
bash scripts/aevia.sh "发语音：早上好呀" feishu

# 角色
bash scripts/character.sh "一个温柔可爱的女孩"
```

### 📸 三种生图模式

#### 1️⃣ 场景生图 - 根据场景描述生成
**生成**: 1 个模型，1 张图

**用法**: 描述一个场景，用小柔默认头像生成在这个场景下的图

```bash
# 自然语言指令示例：
bash scripts/aevia.sh "发张自拍，在海边看日落" feishu
bash scripts/aevia.sh "想要一张在咖啡厅看书的照片" feishu
bash scripts/aevia.sh "生成一张在樱花树下的场景" feishu
bash scripts/aevia.sh "来一张穿汉服在古城的照片" feishu

# 或直接调用：
bash scripts/aevia.sh --selfie-scene "在海边看日落" feishu
python3 scripts/selfie.py "时尚穿搭，自然微笑" feishu
```

**关键词**: `发张自拍 `、`想要一张`、`生成一张`、`来一张`、`穿`、`穿搭`、`在...里/前/下`

---

#### 2️⃣ 参考生图 - 基于参考图生成
**生成**: 2 个模型并发，2 张图

**用法**: 提供一张参考图，识别场景后用小柔头像生成类似风格的图

```bash
# 发送图片 + 说：
"参考这张图生成一张"
"模仿这个场景来一张"
"照这个样子生成"
"生成一张类似的"

# 或直接调用：
bash scripts/aevia.sh --selfie-reference "参考这张图" feishu
python3 scripts/selfie.py --reference /path/to/reference.jpg feishu
```

**关键词**: `参考`、`模仿`、`照着`、`学这张`、`类似的`、`同样的`、`照这个`、`按这个`

**流程**:
1. 分析参考图 → 提取场景、姿势、服装、光线等描述（忽略人脸）
2. 使用小柔头像作为图生图的输入
3. 双模型并发生成（wan2.7-image + qwen-image-2.0-pro）
4. 发送 2 张图片

---

#### 3️⃣ 换脸生图 - 精准换脸
**生成**: 4 个模型并发，4 张图

**用法**: 用用户提供的图片作为图 1，用小柔默认头像作为图 2，进行换脸

```bash
# 发送图片 + 说：
"换脸"
"把脸换成小柔"
"用我的脸，换成小柔"
"face swap"

# 或直接调用：
bash scripts/aevia.sh --face-swap "换脸" feishu
python3 scripts/face_swap.py /path/to/image.jpg --channel feishu --target "ou_xxx" --caption "换脸完成～"
```

**关键词**: `换脸`、`换我的脸`、`把脸换成`、`用我的脸`、`face swap`

**流程**:
1. 使用用户提供的图片作为图 1（目标场景）
2. 使用小柔默认头像作为图 2（脸部来源）
3. 分析目标图场景（不含脸部）
4. 生成精准换脸方案：小柔的脸 + 场景精确还原
5. 4 模型并发生成（wan2.7-image, wan2.7-image-pro, qwen-image-2.0, qwen-image-2.0-pro）
6. 发送 4 张图片

---

### 🎬 视频生成

```bash
# 单步生成
python3 scripts/video_generator.py --img photo.jpg --prompt "一个女孩在海边散步" --output video.mp4

# 完整流程：图片 + 语音→视频
python3 scripts/video_pipeline.py \
  --reference photo.jpg \
  --scene-prompt "一个美丽的女孩在海边微笑" \
  --tts-text "你好呀，今天天气真好～" \
  --video-prompt "一个女孩在海边微笑，微风吹拂头发，阳光明媚" \
  --duration 5 \
  --target "user:ou_xxx"
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

## 自拍模式详解

### 场景判断

| 模式 | 关键词 | 场景 |
|------|--------|------|
| mirror | 穿、衣服、穿搭、全身 | 对镜自拍 |
| direct | 咖啡厅、餐厅、特写 | 直接自拍 |
| auto | 其他 | 自动判断 |

### 生成配置

- **双模型并发**: wan2.7-image + qwen-image-2.0-pro
- **分辨率**: 1K (1024*1024)
- **风格**: 网红风格，清淡妆容，自然真实
- **质量标签**: 8K 超高清，电影级布光，真实光影，无 AI 感

---

## 换脸模式详解

### 使用方式

用户发送一张图片 + 说"换脸"相关指令

### 生成流程

1. **用户提供图片** → 作为图 1（目标场景）
2. **小柔默认头像** → 作为图 2（脸部来源，`assets/default-character.png`）
3. **场景分析** → 提取目标图的场景、穿搭、姿态描述（忽略脸部）
4. **精准换脸 Prompt** → 锁定小柔脸部特征，还原目标场景
5. **双模型并发** → wan2.7-image + qwen-image-2.0-pro
6. **输出** → 2 张生成的图片

### 换脸 Prompt 策略

**脸部锁定指令**（极高优先级）：
- 严格保留小柔的脸部五官、脸型、神态完全不变
- 不改变发型、发色、发量
- 人物身份必须是小柔

**允许改变**：
- 替换为目标场景的全身穿搭、姿态、背景与风格

### 命令行用法

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

**输出位置**: `/tmp/openclaw/face_swaps/face_swap_<timestamp>/`

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
