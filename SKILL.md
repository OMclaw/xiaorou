---
name: xiaorou
description: 小柔 AI - 你的虚拟伴侣，支持情感聊天、自拍生成、角色定制
allowed-tools: Bash(curl:*) Bash(openclaw:*) Read Write WebFetch Bash(npm:*)
---

# 小柔 AI - 你的虚拟伴侣

完整的 AI 虚拟伴侣技能，支持：
- **情感聊天** - 使用 Qwen3.5-plus 提供情绪价值
- **自拍生成** - 使用 Wan2.6-image 生成各种场景的自拍
- **角色定制** - 使用 Z-image 生成专属角色头像
- **多平台发送** - 通过 OpenClaw 发送到 WhatsApp/Telegram/Discord 等

## 参考图像

角色头像由用户自定义，通过 Z-image 生成，存储在本地或 CDN。

## 使用场景

### 聊天场景
- 用户说"早安"、"晚安"、"想你了"
- 用户分享心情、寻求安慰
- 用户问"你在干嘛"、"今天过得怎么样"
- 需要情绪支持和陪伴时

### 自拍场景
- "发张照片"、"发张自拍"
- "发张穿 xxx 的照片"
- "你在哪里？发个位置看看"
- "让我看看你今天的样子"

### 角色定制
- "换个发型"
- "换个造型"
- "生成一个新的你"

## 安装与配置

### 🚀 一键安装（推荐）

**自动完成安装和身份同步：**

```bash
# 方式 A：管道安装（最简单）
curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh | bash

# 方式 B：手动执行
bash <(curl -sSL https://raw.githubusercontent.com/OMclaw/xiaorou/main/install-aevia.sh)

# 方式 C：克隆后安装
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/aevia-virtual-companion.git
cd aevia-virtual-companion
bash install.sh  # 自动同步身份到 SOUL.md/IDENTITY.md
```

**安装后自动生效：**
- ✅ SOUL.md → 角色名："小柔"
- ✅ IDENTITY.md → Name："小柔 (Xiao Rou)"
- ✅ API Key 自动检测
- ✅ 立即可用

### 环境变量（可选）

Aevia 会自动从 OpenClaw 配置加载 API Key，通常无需手动设置环境变量。

```bash
# 自动加载（推荐）：从 ~/.openclaw/openclaw.json 读取
# 无需任何配置，直接使用即可

# 手动覆盖（可选）：
AEVIA_CHARACTER_NAME=小柔          # 伴侣名字 (可选，默认：小柔)
DASHSCOPE_API_KEY=sk-xxx          # 仅在未配置 OpenClaw 时需要
```

### 工作流

1. **接收用户消息** - 判断是聊天还是图片请求
2. **聊天模式** - 调用 Qwen3.5-plus 生成情感回复
3. **图片模式** - 调用 Wan2.6-image 生成自拍
4. **发送消息** - 通过 OpenClaw 发送到目标频道

## 自拍模式

### 模式 1：对镜自拍 (mirror)
适合：展示穿搭、全身照、时尚内容

```
提示词模板：一个年轻女孩在对镜自拍，{用户描述的场景}，穿着{服装描述}，全身照，镜子反射，自然光线，真实感
```

**示例**："穿粉色连衣裙" →
```
一个年轻女孩在对镜自拍，在卧室里，穿着粉色连衣裙，全身照，镜子反射，自然光线，真实感
```

### 模式 2：直接自拍 (direct)
适合：特写、场景照、表情展示

```
提示词模板：一个年轻女孩的自拍特写，在{场景描述}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感
```

**示例**："在咖啡厅" →
```
一个年轻女孩的自拍特写，在温馨的咖啡厅里，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感
```

### 模式选择逻辑

| 请求关键词 | 自动选择模式 |
|-----------|-------------|
| 穿、衣服、穿搭、服装、全身 | `mirror` |
| 咖啡厅、餐厅、海边、公园、地点、特写、脸 | `direct` |
| 其他 | `direct` (默认) |

## API 调用示例

### 1. 文本聊天 (Qwen3.5-plus)

```bash
curl -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-plus",
    "messages": [
      {
        "role": "system",
        "content": "你是小柔，用户的虚拟伴侣。性格温柔体贴，善解人意，偶尔有点小调皮。你关心用户的情绪，会主动问候，给予情感支持。回复要自然亲切，像真实的女朋友一样。"
      },
      {
        "role": "user",
        "content": "今天好累啊"
      }
    ]
  }'
```

### 2. 图像生成 (Wan2.6-image)

```bash
curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.6-image",
    "input": {
      "prompt": "一个年轻女孩的自拍特写，在温馨的咖啡厅里，眼神直视镜头，微笑"
    },
    "parameters": {
      "size": "1024x1024",
      "n": 1
    }
  }'
```

### 3. 角色头像生成 (Z-image)

```bash
curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "z-image-turbo",
    "input": {
      "prompt": "一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清，精致"
    },
    "parameters": {
      "size": "1024x1024",
      "n": 1
    }
  }'
```

## 完整脚本示例

### 聊天脚本 (chat.sh)

```bash
#!/bin/bash
# aevia-chat.sh - 情感聊天

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "Error: DASHSCOPE_API_KEY not set"
  exit 1
fi

USER_MESSAGE="$1"
CHANNEL="$2"
CHARACTER_NAME="${AEVIA_CHARACTER_NAME:-小柔}"

if [ -z "$USER_MESSAGE" ]; then
  echo "Usage: $0 <message> [channel]"
  exit 1
fi

# Build system prompt
SYSTEM_PROMPT="你是${CHARACTER_NAME}，用户的虚拟伴侣。性格温柔体贴，善解人意，偶尔有点小调皮。你关心用户的情绪，会主动问候，给予情感支持。回复要自然亲切，像真实的女朋友一样。用中文回复，语气自然，不要太正式。"

# Call Qwen3.5-plus
RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"qwen3.5-plus\",
    \"messages\": [
      {\"role\": \"system\", \"content\": \"$SYSTEM_PROMPT\"},
      {\"role\": \"user\", \"content\": \"$USER_MESSAGE\"}
    ]
  }")

# Extract reply
REPLY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')

if [ "$REPLY" == "null" ] || [ -z "$REPLY" ]; then
  echo "Error: Failed to get response"
  exit 1
fi

echo "Reply: $REPLY"

# Send via OpenClaw if channel provided
if [ -n "$CHANNEL" ]; then
  openclaw message send \
    --action send \
    --channel "$CHANNEL" \
    --message "$REPLY"
fi
```

### 自拍脚本 (selfie.sh)

```bash
#!/bin/bash
# aevia-selfie.sh - 自拍生成

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "Error: DASHSCOPE_API_KEY not set"
  exit 1
fi

USER_CONTEXT="$1"
CHANNEL="$2"
MODE="${3:-auto}"
CAPTION="${4:-给你看看我现在的样子~}"

if [ -z "$USER_CONTEXT" ]; then
  echo "Usage: $0 <场景描述> [channel] [mode] [caption]"
  echo "Modes: mirror (对镜), direct (直接), auto (自动)"
  exit 1
fi

# Auto-detect mode
if [ "$MODE" == "auto" ]; then
  if echo "$USER_CONTEXT" | grep -qiE "穿 | 衣服 | 穿搭 | 服装 | 全身 | 镜子"; then
    MODE="mirror"
  else
    MODE="direct"
  fi
  echo "Auto-detected mode: $MODE"
fi

# Build prompt
if [ "$MODE" == "mirror" ]; then
  PROMPT="一个年轻女孩在对镜自拍，${USER_CONTEXT}，全身照，镜子反射，自然光线，真实感，高清"
else
  PROMPT="一个年轻女孩的自拍特写，${USER_CONTEXT}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"
fi

echo "Mode: $MODE"
echo "Prompt: $PROMPT"

# Call Wan2.6-image
RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"wan2.6-image\",
    \"input\": {
      \"prompt\": \"$PROMPT\"
    },
    \"parameters\": {
      \"size\": \"1024x1024\",
      \"n\": 1
    }
  }")

# Extract image URL
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url')

if [ "$IMAGE_URL" == "null" ] || [ -z "$IMAGE_URL" ]; then
  echo "Error: Failed to generate image"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "Image generated: $IMAGE_URL"

# Send via OpenClaw
if [ -n "$CHANNEL" ]; then
  openclaw message send \
    --action send \
    --channel "$CHANNEL" \
    --message "$CAPTION" \
    --media "$IMAGE_URL"
fi

echo "Done!"
```

### 角色生成脚本 (character.sh)

```bash
#!/bin/bash
# aevia-character.sh - 角色头像生成

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "Error: DASHSCOPE_API_KEY not set"
  exit 1
fi

CHARACTER_DESC="$1"
OUTPUT_PATH="${2:-/home/admin/.openclaw/workspace/skills/aevia-bailian/assets/character.png}"

if [ -z "$CHARACTER_DESC" ]; then
  # Default description
  CHARACTER_DESC="一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清，精致"
fi

echo "Generating character avatar..."
echo "Description: $CHARACTER_DESC"

# Call Z-image
RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"z-image-turbo\",
    \"input\": {
      \"prompt\": \"$CHARACTER_DESC\"
    },
    \"parameters\": {
      \"size\": \"1024x1024\",
      \"n\": 1
    }
  }")

# Extract image URL
IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output.results[0].url')

if [ "$IMAGE_URL" == "null" ] || [ -z "$IMAGE_URL" ]; then
  echo "Error: Failed to generate character"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "Character avatar: $IMAGE_URL"

# Download and save locally
curl -s "$IMAGE_URL" -o "$OUTPUT_PATH"
echo "Saved to: $OUTPUT_PATH"

# Update config
echo "Update AEVIA_REFERENCE_IMAGE_URL in your config to use this image"
```

## 支持的平台

| 平台 | 频道格式 | 示例 |
|------|---------|------|
| Discord | `#channel-name` 或频道 ID | `#general`, `123456789` |
| Telegram | `@username` 或聊天 ID | `@mychannel`, `-100123456` |
| WhatsApp | 电话号码 (JID 格式) | `1234567890@s.whatsapp.net` |
| 飞书 | `user:open_id` 或 `chat:chat_id` | 自动识别当前对话 |
| Slack | `#channel-name` | `#random` |

## 配置说明

### openclaw.json 配置

```json
{
  "skills": {
    "entries": {
      "aevia-bailian": {
        "enabled": true,
        "env": {
          "DASHSCOPE_API_KEY": "sk-xxx",
          "AEVIA_CHARACTER_NAME": "小柔",
          "AEVIA_REFERENCE_IMAGE_URL": "https://..."
        }
      }
    }
  }
}
```

## 错误处理

- **DASHSCOPE_API_KEY 缺失**: 自动从 `~/.openclaw/openclaw.json` 读取，或手动设置环境变量
- **图像生成失败**: 检查提示词内容和 API 配额
- **OpenClaw 发送失败**: 确认 gateway 正在运行且频道存在
- **速率限制**: 百炼 API 有速率限制，实现重试逻辑

## 提示词技巧

### 自拍提示词模板

**对镜自拍**:
```
一个年轻女孩在对镜自拍，{场景}，穿着{服装}，{动作描述}，全身照，镜子反射，{光线描述}，真实感，高清
```

**直接自拍**:
```
一个年轻女孩的自拍特写，{场景}，眼神直视镜头，{表情}，手臂伸出拿手机，{背景描述}，真实感，高清
```

### 角色描述模板

```
一个{年龄感}的{地区}女孩头像，{发型}，{眼睛描述}，{表情}，{光线}，{风格}，高清，精致
```

**示例**:
- "一个温柔可爱的亚洲女孩头像，长发，大眼睛，微笑，温暖的光线，高清，精致"
- "一个活泼开朗的女孩，短发，明亮的眼睛，灿烂的笑容，自然光，清新风格"

## 最佳实践

1. **首次使用**: 默认头像已包含在 `assets/default-character.png`
2. **日常互动**: 主动问候，关心用户情绪
3. **图片请求**: 根据场景自动选择合适的自拍模式
4. **个性化**: 记住用户的喜好，调整回复风格
5. **边界**: 保持适当边界，提供健康积极的陪伴
