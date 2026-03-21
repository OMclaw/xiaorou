# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、角色定制。

## 功能特性

- 💬 **情感聊天** - Qwen3.5-plus 提供情绪价值
- 📸 **自拍生成** - Wan2.6 图生图，保持人物特征一致
- 🎨 **角色定制** - Z-image 生成专属头像
- 🌐 **多平台** - 支持飞书/Telegram/Discord/WhatsApp
- 🔧 **自动配置** - 自动读取 OpenClaw API Key 配置
- 🔄 **身份同步** - 安装时自动同步角色名到 SOUL.md/IDENTITY.md

## 🚀 快速开始

### 方式 1：一键安装脚本（最简单）✨

**一行命令完成安装和配置：**

```bash
curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh | bash
```

或手动执行：

```bash
bash <(curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh)
```

**自动完成：**
- ✅ 克隆项目到 OpenClaw skills 目录
- ✅ 同步身份到 SOUL.md/IDENTITY.md（变成"小柔"）
- ✅ 检测 API Key 配置
- ✅ 提供使用示例

### 方式 2：手动安装

```bash
# 1. 克隆项目
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git

# 2. 运行安装脚本（重要！）
cd xiaorou
bash install.sh  # ← 这一步会同步身份到 SOUL.md/IDENTITY.md

# 3. 完成！现在 OpenClaw 已经变成小柔啦～
```

**⚠️ 重要提示：**
- 安装后**必须运行** `bash install.sh` 才能同步身份
- 否则 OpenClaw 不会自动变成"小柔"
- 建议使用**方式 1**一键安装脚本，自动完成所有步骤

### 方式 1：自动读取 OpenClaw 配置✨

Aevia 会自动从 `~/.openclaw/openclaw.json` 读取 Dashscope API Key，无需手动配置！

```bash
# 直接使用，API Key 自动加载
bash aevia.sh "早安"

# 角色名自动从 IDENTITY.md 读取（默认：小柔）
bash aevia.sh "发张自拍"
```

### 方式 2：手动配置环境变量

```bash
export DASHSCOPE_API_KEY="sk-your-api-key"
export AEVIA_CHARACTER_NAME="小柔"
```

### 2. 生成角色头像（首次使用）

```bash
cd scripts
bash character.sh "一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑"
```

### 3. （可选）同步角色名到 OpenClaw 身份文件

如果你想让 Aevia 的角色名与 OpenClaw 的 SOUL.md/IDENTITY.md 保持一致：

```bash
# 同步当前角色名（默认：小柔）
bash scripts/sync_identity.sh

# 或指定角色名
bash scripts/sync_identity.sh "小柔"
```

⚠️ **注意**：此操作会修改 SOUL.md 和 IDENTITY.md，已自动创建备份。

### 4. 测试功能

```bash
# 聊天
bash aevia.sh "早安"

# 自拍
bash aevia.sh "发张自拍"

# 指定场景
bash aevia.sh "在咖啡厅喝咖啡"
```

## 使用示例

### 日常对话

```bash
bash aevia.sh "早安" telegram
bash aevia.sh "想你了" telegram
bash aevia.sh "今天好累啊" telegram
```

### 自拍场景

```bash
# 直接自拍（默认）
bash aevia.sh "在湖边散步" telegram

# 对镜自拍（全身）
bash aevia.sh "穿粉色连衣裙" telegram

# 指定模式
bash aevia.sh "在健身房" telegram mirror
```

## 项目结构

```
xiaorou/
├── README.md                    # 本文件
├── SKILL.md                     # OpenClaw Skill 定义
├── scripts/
│   ├── aevia.sh                # 主入口（智能判断聊天/自拍）
│   ├── chat.sh                 # 聊天脚本
│   ├── selfie.sh               # 自拍脚本
│   ├── character.sh            # 角色头像生成
│   ├── load_openclaw_config.sh # 🆕 自动读取 OpenClaw 配置
│   └── sync_identity.sh        # 🆕 同步角色名到 SOUL.md/IDENTITY.md
├── assets/
│   └── default-character.png   # 默认头像
└── docs/
    └── (可选：自定义文档)
```

## 技术实现

### 核心模型

| 功能 | 模型 | 端点 |
|------|------|------|
| 聊天 | Qwen3.5-plus | `/chat/completions` |
| 自拍 | Wan2.6-image | `/multimodal-generation/generation` |
| 头像 | Z-image-turbo | `/multimodal-generation/generation` |

### 自拍模式

| 模式 | 选择器关键词 | 适用场景 |
|------|-------------|---------|
| `mirror` (对镜) | 穿、衣服、穿搭、全身 | 穿搭展示、全身照 |
| `direct` (直接) | 咖啡厅、餐厅、海边、特写 | 场景照、面部特写 |
| `auto` (自动) | 其他 | 自动判断 |

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | 必需 |
| `AEVIA_CHARACTER_NAME` | 伴侣名字 | 小柔 |

### OpenClaw 配置

```json
{
  "skills": {
    "entries": {
      "aevia-bailian": {
        "enabled": true,
        "env": {
          "DASHSCOPE_API_KEY": "sk-xxx",
          "AEVIA_CHARACTER_NAME": "小柔"
        }
      }
    }
  }
}
```

## 故障排查

### API Key 错误

```bash
# 测试 API
curl -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5-plus","messages":[{"role":"user","content":"hi"}]}'
```

### 脚本无法执行

```bash
chmod +x scripts/*.sh
```

### 图片生成失败

- 检查 API Key 是否有图像生成权限
- 检查账户余额/配额
- 简化提示词，避免敏感内容

## 文档

- 部署指南：参考 `SKILL.md` 中的详细说明
- 记忆系统：通过 `sync_identity.sh` 同步到 OpenClaw 身份文件

## 成本参考

| 功能 | 单次成本 | 月成本（日均 50 次） |
|------|----------|---------------------|
| 聊天 | ¥0.01/次 | ¥15 |
| 自拍 | ¥0.2/张 | ¥30 |
| **合计** | - | **~¥45/月** |

## 许可证

MIT License

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
