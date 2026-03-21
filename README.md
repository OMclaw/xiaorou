# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、角色定制。

## 功能特性

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成各种场景的自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🎙️ **语音消息** - CosyVoice-v3-flash 高质量 TTS
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
│   ├── tts.sh             # TTS Shell 封装
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

**支持以下音色**（默认：longqiang_v3 成熟男声）：

| 音色 | 描述 |
|------|------|
| `longqiang_v3` | 成熟男声（默认）⭐ |
| `longxiaochun_v2` | 温柔女声 |
| `longxiaoman_v2` | 活泼女声 |
| `longxiaoxia_v2` | 知性女声 |
| `longxiaoyu_v2` | 甜美女声 |
| `longxiaoyan_v2` | 成熟女声 |
| `longanyang` | 阳光男声 |

**手动指定音色：**
```bash
python3 scripts/tts.py --text "你好" --voice longxiaochun_v2 --output /tmp/voice.mp3
```

**使用 Shell 脚本：**
```bash
bash scripts/tts.sh "你好，我是小柔" /tmp/voice.mp3 longqiang_v3
```

### 🤖 模型选择

默认使用 `cosyvoice-v3-flash` 模型，支持：

- `cosyvoice-v3-flash` - 快速高质量（默认）
- `cosyvoice-v3-plus` - 更高质量（稍慢）

## 🎯 高级用法

### 直接使用 Python API

```python
from scripts.tts import text_to_speech

success, message = text_to_speech(
    text="你好，我是小柔",
    output_path="/tmp/voice.mp3",
    voice="longqiang_v3",
    model="cosyvoice-v3-flash"
)

if success:
    print(f"生成成功：{message}")
else:
    print(f"生成失败：{message}")
```

### 批量生成

```bash
# 生成多个语音文件
for text in "早上好" "中午好" "晚上好"; do
    bash scripts/tts.sh "$text" "/tmp/$text.mp3" longqiang_v3
done
```

## 🧪 测试

```bash
# 运行 TTS 测试
python3 scripts/test_tts.py

# 列出可用音色
python3 scripts/tts.py --list-voices

# 测试单句生成
python3 scripts/tts.py "测试语音" /tmp/test.mp3 longqiang_v3
```

## ❓ 常见问题

### Q: 语音生成失败？
A: 检查 API Key 是否正确设置：
```bash
echo $DASHSCOPE_API_KEY
# 应该显示 sk-xxx 格式的 Key
```

### Q: 如何更改音色？
A: 在调用时指定 `--voice` 参数，或修改 `tts.py` 中的 `DEFAULT_VOICE` 常量。

### Q: 生成的语音质量不好？
A: 尝试使用 `cosyvoice-v3-plus` 模型：
```bash
python3 scripts/tts.py --text "你好" --model cosyvoice-v3-plus --output /tmp/voice.mp3
```

## 📚 更多帮助

安装后查看 `SKILL.md` 获取详细文档。

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**

**TTS 引擎**: 阿里云 CosyVoice-v3
