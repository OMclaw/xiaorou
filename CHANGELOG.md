# Changelog

All notable changes to this project will be documented in this file.

## [3.5.5] - 2026-03-23

### ✨ Added
- **向量化动态配置支持**：支持 `AEVIA_CHANNEL` 和 `AEVIA_TARGET` 环境变量
- `CHANNEL` 参数改为第 2 个可选参数，向后兼容
- `TARGET` 支持第 3 个参数或环境变量覆盖

### 🔧 Fixed
- **修复飞书私聊消息丢失问题**：将默认 `SEND_TARGET` 从 `chat:oc_xxx` 改为 `user:ou_xxx`
- 语音模式和聊天模式的 target 配置保持一致

### 📝 Changed
- `aevia.sh` 默认频道从硬编码改为 `AEVIA_CHANNEL` 环境变量
- `aevia.sh` 默认 target 从硬编码改为 `AEVIA_TARGET` 环境变量
- 默认值统一为飞书私聊格式 `user:ou_0668d1ec503978ef15adadd736f34c46`

### 🛡️ Security
- **Prompt Injection 防护**：`tts.py` 增加敏感词检测，拒绝可疑输入

### ✅ Compatibility
- ✅ 向后兼容：仍支持直接传参 `bash aevia.sh "消息" "频道" "target"`
- ✅ 环境变量优先级：命令行 > 环境变量 > 默认值

---

## [3.5.0] - 2026-03-23

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
