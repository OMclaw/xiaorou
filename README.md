# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、角色定制。

## 功能特性

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成各种场景的自拍
- 🎨 **角色定制** - Z-image 生成专属头像
- 🌐 **多平台** - 支持飞书/Telegram/Discord/WhatsApp
- 🔧 **自动配置** - 自动读取 OpenClaw API Key

## 🚀 快速安装

```bash
curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh | bash
```

或手动安装：

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git
cd xiaorou && bash install.sh
```

## 💬 使用示例

```bash
# 聊天
bash scripts/aevia.sh "早安"

# 自拍
bash scripts/aevia.sh "发张自拍" feishu

# 指定场景
bash scripts/aevia.sh "在咖啡厅喝咖啡" feishu

# 角色定制
bash scripts/character.sh "一个温柔可爱的亚洲女孩"
```

## 📁 项目结构

```
xiaorou/
├── README.md
├── SKILL.md
├── install.sh
├── install-aevia.sh
├── scripts/
│   ├── aevia.sh         # 主入口（聊天 + 自拍）
│   └── character.sh     # 角色头像生成
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

## 📚 更多帮助

安装后查看 `SKILL.md` 获取详细文档。

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
