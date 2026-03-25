# Changelog

All notable changes to this project will be documented in this file.

## [3.5.6] - 2026-03-25

### ✨ Added
- **飞书语音气泡原生支持**：msg_type=audio 原生支持
- **集成 li-feishu-audio 技能**
- **CosyVoice OPUS 直传**：直接生成 OPUS 格式，无需 ffmpeg 转换

### 🔧 Optimized
- **环境变量支持**：支持 `AEVIA_FEISHU_SKILL_DIR` 配置
- **降级处理**：技能不可用时回退到普通发送
- **非飞书平台优化**：语音发送逻辑优化

### 📦 Technical Details
- ✅ OPUS 24kHz 单声道，符合飞书要求
- ✅ 自动从 `openclaw.json` 读取飞书凭证
- ✅ 零敏感信息提交，配置可移植

---

## [3.5.5] - 2026-03-24

### ✨ Added
- **API Key 兼容性增强**：`selfie.py` 现在支持从 `~/.openclaw/openclaw.json` 读取 API Key
- 支持两种配置路径：
  - `.models.providers.dashscope.apiKey`
  - `.skills.entries.xiaorou.env.DASHSCOPE_API_KEY`
- 完善的日志输出，方便调试

### 🔧 Fixed
- 修复了定时任务环境中自拍功能无法读取 API Key 的问题
- 修复了 crontab 环境下环境变量未设置导致的失败

### 📝 Changed
- `validate_config()` 函数重构，与 `tts.py` 保持一致
- 改进错误提示信息

### ✅ Compatibility
- ✅ 向后兼容：仍支持环境变量 `DASHSCOPE_API_KEY`
- ✅ OpenClaw 集成：自动读取 `openclaw.json` 配置
- ✅ 定时任务友好：无需在 crontab 中设置环境变量

---

## [3.0.0] - 2026-03-22

### ✨ Added
- CosyVoice-v3-flash 语音合成
- 飞书语音气泡支持
- 多平台发送（飞书/Telegram/Discord/WhatsApp）

### 🔧 Changed
- 项目结构精简优化
- 删除冗余脚本

---

## [2.2.0] - 2026-03-20

### ✨ Added
- 性能优化
- 自拍生成优化

---

## [2.0.0] - 2026-03-18

### ✨ Added
- 重大功能更新

---

## [1.0.0] - 2026-03-15

### ✨ Added
- 初始版本发布
