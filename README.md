# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、角色定制。

## 功能特性

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成各种场景的自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🎙️ **语音消息** - CosyVoice-v3.5-plus 温柔女声 TTS
- 🌐 **多平台** - 支持飞书/Telegram/Discord/WhatsApp
- 🔧 **自动配置** - 自动读取 OpenClaw API Key

## 🚀 快速安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git
cd xiaorou && bash install.sh
```

**更新：**

```bash
cd ~/.openclaw/workspace/skills/xiaorou
git pull && bash install.sh
```

## 💬 使用示例

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 自拍
bash scripts/aevia.sh "发张自拍" feishu

# 指定场景
bash scripts/aevia.sh "在咖啡厅喝咖啡" feishu

# 🎙️ 语音消息（文字转语音）
bash scripts/aevia.sh "发语音：早上好呀" feishu
bash scripts/aevia.sh "语音消息：今天也要加油哦" feishu
bash scripts/aevia.sh "说句话：我想你了" feishu

# 角色定制
bash scripts/character.sh "一个温柔可爱的亚洲女孩"
```

## 📁 项目结构

```
xiaorou/
├── README.md
├── SKILL.md
├── install.sh              # 安装脚本
├── scripts/
│   ├── aevia.sh           # 主入口（聊天 + 自拍 + 语音）
│   ├── tts.py             # 文字转语音（CosyVoice）
│   ├── selfie.py          # 自拍生成（核心）
│   └── character.sh       # 角色头像生成
└── assets/
    └── default-character.png
```

## 🔑 配置说明

Aevia 会自动从 `~/.openclaw/openclaw.json` 读取 API Key，无需手动配置。

如需手动设置：

```bash
export DASHSCOPE_API_KEY="sk-your-api-key"
export AEVIA_CHARACTER_NAME="小柔"
```

### 🎙️ TTS 配置

语音功能使用相同的 `DASHSCOPE_API_KEY`，无需额外配置。

**依赖要求：**
- Python 3.9+（使用 Linuxbrew 安装）
- dashscope SDK（阿里云官方）
- ffmpeg（用于 OPUS 格式转换）

安装依赖：
```bash
# Python 3.9（如果还没有）
brew install python@3.9

# dashscope SDK
/home/linuxbrew/.linuxbrew/bin/python3.9 -m pip install dashscope

# ffmpeg（用于音频转换）
brew install ffmpeg
```

**支持音色**（CosyVoice-v3-flash，默认：longanyang 温暖女声）：
- `longanyang` - 温暖女声（推荐，默认）
- `longxiaochun` - 青春女声
- `longcheng` - 成熟男声
- `longxiaoyu` - 甜美女声
- `longxiaoxia` - 知性女声

**输出格式：**
- 飞书：自动转换为 OPUS 格式（显示语音气泡）
- 其他平台：使用 MP3 格式

手动指定音色：
```bash
/home/linuxbrew/.linuxbrew/bin/python3.9 scripts/tts.py --text "你好" --voice longanyang --output /tmp/voice.mp3
```

## 📚 更多帮助

安装后查看 `SKILL.md` 获取详细文档。

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
