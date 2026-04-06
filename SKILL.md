---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、视频生成、语音消息
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write Bash(python3:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus
- 📸 **自拍生成** - wan2.7-image / qwen-image-2.0-pro
- 🔄 **参考生图** - 1 个模型（wan2.7-image），1 张图
- 🎬 **视频生成** - wan2.6-i2v（图片 + 文字 → 视频）
- 🎨 **角色定制** - Z-image
- 🎙️ **语音消息** - CosyVoice-v3-flash（飞书语音气泡）
- 🌐 **多平台** - 飞书/Telegram/Discord/WhatsApp

## 依赖

**必须**：
- Python 3.9+
- `dashscope`（阿里云大模型 SDK）：`pip3 install dashscope`
- `requests`（HTTP 库，通常已预装）

**无其他第三方依赖**：不需要 ffmpeg、insightface、opencv 等。

## 安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git
cd xiaorou && pip3 install dashscope
```

## 使用

### 💬 基础用法

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 语音
bash scripts/aevia.sh "发语音：早上好呀" feishu

# 角色定制（通过聊天指令）
# 示例："帮我生成一个温柔可爱的角色"
```

### 📸 两种生图模式

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

**关键词**: `参考`、`模仿`、`照着/照著`、`学这张`、`类似的`、`同样的`、`照这个`、`按这个`、`生成一张`、`来一张`

**流程**:
1. 分析参考图 → 提取场景、姿势、服装、光线等描述（忽略人脸）
2. 使用小柔头像作为图生图的输入
3. 单模型生成（wan2.7-image）
4. 发送 1 张图片

---

## 配置

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

- **场景生图**：1 模型（wan2.7-image），1 张图
- **参考生图**：1 模型（wan2.7-image），1 张图
- **分辨率**：1K (1024*1024)
- **风格**：网红风格，清淡妆容，自然真实
- **质量标签**：8K 超高清，电影级布光，真实光影，无 AI 感

---

## API

- 聊天：Qwen3.5-plus
- 自拍：wan2.7-image / qwen-image-2.0-pro
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
| duration | 视频时长 | 5 秒 |
| audio | 是否启用音频 | false |
| prompt_extend | 是否扩展提示词 | false |

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
