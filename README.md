# 小柔 AI - 你的虚拟伴侣 🦞❤️

AI 驱动的虚拟伴侣，支持情感聊天、自拍生成、视频生成、语音消息。

## ✨ 功能特性

- 💬 **情感聊天** - Qwen3.6-Plus 提供温暖陪伴
- 📸 **场景生图** - wan2.7-image 根据文字描述生成小柔自拍
- 🖼️ **参考生图** - wan2.7-image + qwen-image-2.0-pro 双模型并发，基于参考图生成
- 🎬 **视频生成** - wan2.6-i2v 图片转视频
- 🎙️ **语音消息** - CosyVoice-v3-flash 温柔女声 TTS（飞书语音气泡）
- 🌐 **多平台** - 支持飞书 / Telegram / Discord / WhatsApp
- 🔧 **自动配置** - 自动读取 OpenClaw API Key，零配置启动

## 🚀 快速安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/OMclaw/xiaorou.git
```

**依赖（仅需 2 个 Python 库）：**
```bash
pip3 install dashscope requests
```

> ✅ 无其他第三方依赖：不需要 ffmpeg、insightface、opencv、numpy 等。

**更新：**
```bash
cd ~/.openclaw/workspace/skills/xiaorou && git pull
```

## 💬 使用示例

### 情感聊天
```bash
bash scripts/aevia.sh "早安"
```

### 📸 场景生图（文字 → 图片）
```bash
# 自然语言
bash scripts/aevia.sh "发张自拍，在海边看日落" feishu
bash scripts/aevia.sh "想要一张在咖啡厅看书的照片" feishu

# 直接调用
python3 scripts/selfie.py "时尚穿搭，自然微笑" feishu
```

**关键词**：发张自拍、想要一张、生成一张、来一张、穿、穿搭、在...里/前/下

### 🖼️ 参考生图（参考图 → 图片，双模型并发）
```bash
# 发送图片 + 说：
"参考这张图生成一张"
"模仿这个场景来一张"
"照这个样子生成"
"生成一张类似的"
```

**关键词**：参考、模仿、照着/照著、学这张、类似的、同样的、照这个、按这个、生成一张、来一张

### 🎬 视频生成（图片 → 视频）
```bash
python3 scripts/generate_video.py \
  --image /path/to/photo.jpg \
  --prompt "一个女孩在海边微笑" \
  --target "user:ou_xxx"
```

### 🎙️ 语音消息（文字 → 语音气泡）
```bash
bash scripts/aevia.sh "发语音：早上好呀" feishu
bash scripts/aevia.sh "语音消息：今天也要加油哦" feishu

# 直接调用
python3 scripts/tts.py "你好，我是小柔" /tmp/voice.opus --channel feishu
```

## 📁 项目结构

```
xiaorou/
├── README.md
├── SKILL.md                  # 详细功能文档
├── CHANGELOG.md              # 版本更新记录
├── install.sh                # 安装脚本
├── scripts/
│   ├── aevia.sh              # 统一入口（聊天 + 自拍 + 语音）
│   ├── selfie.py             # 自拍生成（场景 + 参考）
│   ├── image_analyzer.py     # 参考图分析（多模态视觉）
│   ├── generate_video.py     # 视频生成（wan2.6-i2v）
│   ├── tts.py                # 文字转语音（CosyVoice）
│   ├── config.py             # 统一配置模块
│   └── test_mode_detection.sh # 模式检测测试
└── assets/
    └── default-character.png # 小柔默认头像
```

## 🔑 配置说明

小柔 AI 会自动从 `~/.openclaw/openclaw.json` 读取 API Key，**无需手动配置**。

如需手动设置：
```bash
export DASHSCOPE_API_KEY="sk-your-api-key"
```

### 🎙️ TTS 语音配置

**默认音色**：`longyingxiao_v3`（温柔女声）

**所有可用音色**：
| 音色 | 说明 |
|------|------|
| `longyingxiao_v3` | 温柔女声（默认） |
| `longanyang` | 温暖女声 |
| `longxiaochun` | 青春女声 |
| `longcheng` | 成熟男声 |
| `longxiaoyu` | 甜美女声 |
| `longxiaoxia` | 知性女声 |

**输出格式**：
- 飞书：OPUS（语音气泡 💬）
- 其他平台：MP3

```bash
# 列出所有音色
python3 scripts/tts.py --list-voices

# 指定音色
python3 scripts/tts.py "你好" /tmp/voice.opus --voice longanyang --channel feishu
```

### 📸 自拍模式

| 模式 | 关键词 | 说明 |
|------|--------|------|
| 场景生图 | 发张自拍、想要一张、生成一张 | 文字描述 → 1 模型 → 1 张图 |
| 参考生图 | 参考、模仿、照着 | 参考图分析 → 2 模型并发 → 2 张图 |

## 🛡️ 安全特性

- ✅ 路径白名单验证（防止路径遍历）
- ✅ 文件大小限制（图片 10MB / 下载 20MB）
- ✅ 输入净化（移除危险字符，保留中文）
- ✅ 日志脱敏（API Key / Bearer Token / OSS 签名）
- ✅ Prompt Injection 检测
- ✅ 原子文件操作（防止 TOCTOU 竞争）

## 📊 项目状态

| 指标 | 数值 |
|------|------|
| 版本 | v5.10.0 |
| 代码文件 | 7 个 |
| 总代码量 | ~2600 行 |
| 第三方依赖 | dashscope + requests |
| Code Review | 9 轮，118+ 问题已修复 |
| 代码质量 | A++ |

## ❓ 常见问题

**Q: 需要安装 ffmpeg 吗？**  
A: 不需要。小柔 AI 已移除所有 ffmpeg 依赖。

**Q: 需要安装 insightface / opencv 吗？**  
A: 不需要。换脸功能已移除，无需这些依赖。

**Q: Python 版本要求？**  
A: Python 3.9+（系统自带即可，无需 Linuxbrew）。

**Q: 语音生成失败？**  
A: 检查 `DASHSCOPE_API_KEY` 是否正确，网络是否畅通。

**Q: 文本长度限制？**  
A: 单次请求最多 500 字。

## 📚 更多帮助

查看详细文档：[SKILL.md](SKILL.md)

---

**让 AI 更有温度，让陪伴更真实 🦞❤️**
