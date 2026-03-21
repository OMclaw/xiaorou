---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、角色定制
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write WebFetch Bash(npm:*)
---

# 小柔 AI - 你的虚拟伴侣

## 功能

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6-image 生成自拍
- 🎨 **角色定制** - Z-image 生成专属头像
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

## API

- 聊天：Qwen3.5-plus
- 自拍：Wan2.6-image
- 头像：Z-image-turbo

## 更多

查看 README.md 获取完整文档。
