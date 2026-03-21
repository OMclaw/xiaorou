# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、角色定制。

## 功能特性

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成各种场景的自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🎙️ **语音消息** - CosyVoice-v3-flash 温柔女声 TTS
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
├── requirements.txt        # Python 依赖
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

**安装依赖：**
```bash
brew install python@3.9
/home/linuxbrew/.linuxbrew/bin/python3.9 -m pip install dashscope
brew install ffmpeg
```

**支持音色**（CosyVoice-v3-flash，默认：longyingxiao_v3 温柔女声）：
- `longyingxiao_v3` - 温柔女声（推荐，默认）
- `longanyang` - 温暖女声
- `longxiaochun` - 青春女声
- `longcheng` - 成熟男声
- `longxiaoyu` - 甜美女声
- `longxiaoxia` - 知性女声

**输出格式：**
- 飞书：自动转换为 OPUS 格式（显示语音气泡）
- 其他平台：使用 MP3 格式

**手动指定音色：**
```bash
/home/linuxbrew/.linuxbrew/bin/python3.9 scripts/tts.py --text "你好" --voice longanyang --output /tmp/voice.mp3
```

### 📸 自拍模式

| 模式 | 关键词 | 场景 |
|------|--------|------|
| mirror | 穿、衣服、穿搭、全身 | 对镜自拍 |
| direct | 咖啡厅、餐厅、特写 | 直接自拍 |
| auto | 其他 | 自动判断 |

## 🎙️ TTS 高级用法

### 直接使用 Python 脚本

```bash
# 基础用法
python3 scripts/tts.py "你好，我是小柔" /tmp/voice.mp3

# 选择音色
python3 scripts/tts.py --text "你好" --voice longxiaoxia --output /tmp/voice.mp3

# 列出可用音色
python3 scripts/tts.py --list-voices
```

### 编程调用

```python
from scripts.tts import text_to_speech

success, message = text_to_speech(
    text="你好，我是小柔",
    output_path="/tmp/voice.mp3",
    voice="longyingxiao_v3"
)
```

### 常见问题

**Q: 语音生成失败？**  
A: 检查 API Key 是否正确设置，网络连接是否正常。

**Q: 文本长度限制？**  
A: 单次请求最多 500 字。

**Q: 临时文件会清理吗？**  
A: 会自动清理，异常退出时可能需要手动清理 `/tmp` 目录。

## 📚 更多帮助

安装后查看 `SKILL.md` 获取详细文档。

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
