# 小柔 AI - 语音合成使用指南

📻 基于阿里云 CosyVoice-v3-flash 的高质量语音合成工具

---

## 🚀 快速开始

### 方式 1：使用统一入口（推荐）

```bash
cd ~/.openclaw/workspace/skills/xiaorou

# 飞书平台
./scripts/aevia.sh "发语音：早上好呀"

# 或指定目标用户
./scripts/aevia.sh "发语音：早上好呀" "user:ou_xxx"
```

**优点**：
- ✅ 自动根据平台选择最优格式
- ✅ 自动清理临时文件
- ✅ 输入安全净化

---

### 方式 2：直接调用 tts.py

#### 基础用法

```bash
# 飞书平台（自动生成 OPUS 格式）
python3 scripts/tts.py "我好想你呀" /tmp/voice --channel feishu

# Telegram/Discord（自动生成 MP3 格式）
python3 scripts/tts.py "Hello" /tmp/voice --channel telegram

# WhatsApp（自动生成 OPUS 格式）
python3 scripts/tts.py "Hello" /tmp/voice --channel whatsapp
```

#### 使用环境变量（推荐）

```bash
# 设置默认平台
export AEVIA_CHANNEL=feishu

# 然后直接使用，自动选择 OPUS 格式
python3 scripts/tts.py "早上好呀" /tmp/voice

# 或让脚本自动添加后缀
python3 scripts/tts.py "早上好呀" /tmp/voice_message
```

#### 向后兼容

```bash
# 直接指定文件格式（保持向后兼容）
python3 scripts/tts.py "早上好呀" /tmp/voice.opus
python3 scripts/tts.py "Hello" /tmp/voice.mp3
```

---

## 📋 参数说明

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `text` | 待转换的文本 | `"早上好呀"` |
| `output` | 输出文件路径 | `/tmp/voice` |

### 可选参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--channel` | `-c` | `AEVIA_CHANNEL` 环境变量 | 目标平台，自动选择最优格式 |
| `--voice` | `-v` | `longyingxiao_v3` | 音色名称 |
| `--model` | `-m` | `cosyvoice-v3-flash` | 模型名称 |
| `--text` | `-t` | - | 待转换的文本（长文本推荐） |
| `--output` | `-o` | - | 输出文件路径 |
| `--list-voices` | - | - | 列出可用音色 |
| `--verbose` | - | - | 显示详细日志 |

---

## 🎯 平台格式对照表

| 平台 | 推荐格式 | 文件后缀 | 说明 |
|------|---------|---------|------|
| **飞书** | OPUS | `.opus` | 触发语音气泡 ✅ |
| **Telegram** | MP3 | `.mp3` | 推荐格式 |
| **Discord** | MP3 | `.mp3` | 推荐格式 |
| **WhatsApp** | OPUS | `.opus` | 推荐格式 |

---

## 🎨 可用音色

运行以下命令查看所有可用音色：

```bash
python3 scripts/tts.py --list-voices
```

### 推荐音色

| 音色 | 风格 | 适用场景 |
|------|------|---------|
| `longanyang` | 温暖男声 | 新闻播报、有声书 |
| `longxiaochun` | 清新女声 | 客服、助手 |
| `longxiaoxia` | 活泼女声 | 娱乐、互动 |
| `longyingxiao_v3` | 温柔女声（默认） | 情感表达、陪伴 |

---

## 📊 使用示例

### 示例 1：飞书语音气泡

```bash
# 方式 1：使用统一入口（最简单）
./scripts/aevia.sh "发语音：我好想你呀"

# 方式 2：直接调用
python3 scripts/tts.py "我好想你呀" /tmp/voice --channel feishu
openclaw message send --channel feishu --target user:ou_xxx --media /tmp/voice.opus
```

### 示例 2：多平台发布

```bash
# 设置环境变量
export AEVIA_CHANNEL=feishu

# 生成飞书版本（OPUS）
python3 scripts/tts.py "早上好" /tmp/voice_feishu

# 切换到 Telegram
export AEVIA_CHANNEL=telegram

# 生成 Telegram 版本（MP3）
python3 scripts/tts.py "Good morning" /tmp/voice_telegram
```

### 示例 3：批量生成

```bash
#!/bin/bash

texts=("早上好" "中午好" "晚上好")

for text in "${texts[@]}"; do
    python3 scripts/tts.py "$text" "/tmp/greeting_$text" --channel feishu
done
```

---

## ⚠️ 注意事项

### 1. 飞书平台必须使用 OPUS 格式

```bash
# ❌ 错误：MP3 格式会被当作普通文件
python3 scripts/tts.py "早上好" /tmp/voice.mp3

# ✅ 正确：使用 --channel 自动选择 OPUS
python3 scripts/tts.py "早上好" /tmp/voice --channel feishu

# ✅ 正确：手动指定 OPUS 后缀
python3 scripts/tts.py "早上好" /tmp/voice.opus
```

### 2. 文本长度限制

- 最大长度：500 字符
- 建议长度：50-200 字符（最佳效果）

### 3. 并发限制

- 建议并发数：< 5
- 超过限制可能触发 API 限流

### 4. 文件格式验证

生成的 OPUS 文件会自动验证：
- 采样率：24kHz
- 声道：单声道
- 编码：OPUS

---

## 🔧 故障排查

### 问题 1：飞书收到的是文件不是语音气泡

**原因**：使用了 MP3 格式

**解决**：
```bash
# 使用 --channel 参数
python3 scripts/tts.py "文本" /tmp/voice --channel feishu
```

### 问题 2：音色警告

```
WARNING - 音色 'longyingxiao_v3' 不在推荐列表中
```

**说明**：这是正常警告，`longyingxiao_v3` 是特殊音色，可以正常使用。

### 问题 3：API 调用失败

**可能原因**：
- API Key 未配置
- 网络连接问题
- API 限流

**解决**：
```bash
# 检查 API Key
cat ~/.openclaw/openclaw.json | jq '.models.providers.dashscope.apiKey'

# 重试（自动重试 3 次）
python3 scripts/tts.py "文本" /tmp/voice --channel feishu
```

---

## 📚 相关文档

- [小柔 Skills 总览](../README.md)
- [自拍生成指南](./SELFIE_GUIDE.md)
- [视频生成指南](./VIDEO_GUIDE.md)
- [aevia.sh 统一入口](./AEVIA_GUIDE.md)

---

**最后更新**: 2026-04-04  
**维护者**: 小柔 AI Team 🦞
