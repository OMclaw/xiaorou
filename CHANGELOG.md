# Changelog

All notable changes to this project will be documented in this file.

## [4.5.21] - 2026-04-04

### 🐛 Fixed
- **语音格式多平台适配**：根据平台自动选择 OPUS/MP3 格式
- **视频生成多平台支持**：从环境变量读取 channel 和 target
- **临时文件清理**：使用 try/finally 确保清理
- **移除硬编码默认值**：强制通过环境变量配置
- **Python 版本兼容**：从 python3.11 改为 python3

### 🔧 Technical Details
- `aevia.sh`: 根据 AEVIA_CHANNEL 选择音频格式 (feishu→opus, telegram/discord→mp3)
- `generate_video.py`: 移除 FEISHU_TARGET 硬编码，支持 --channel 和 --target 参数
- `selfie.py`: try/finally 确保临时文件清理，支持空 target 配置
- `config.py`: 移除硬编码 open_id 默认值
- 全面使用 `python3` 替代 `python3.11`

### 📊 Impact
✅ 飞书：完全兼容
✅ Telegram：音频格式适配
✅ Discord：音频格式适配
✅ WhatsApp：音频格式适配
✅ 多平台部署：无需修改代码

---

## [4.5.20] - 2026-04-04

### 🐛 Fixed
- **修复飞书跨应用发送图片问题**：统一使用 `openclaw message send` 命令发送图片
- 解决 open_id 跨应用权限限制导致的发送失败

### 🔧 Technical Details
- 移除 `send_feishu_image_message()` 和 `upload_feishu_image()` 直接 API 调用
- 所有平台（包括飞书）统一使用 `openclaw message send` 命令
- 代码简化：从双路径处理变为单一路径
- 减少约 30 行代码，降低维护复杂度

### 📊 Impact
- ✅ 飞书发送成功率提升（不再受跨应用限制）
- ✅ 代码复杂度降低
- ✅ 平台一致性提升
- ✅ 全场景回归测试通过

---

## [4.0.0] - 2026-03-30

### ✨ Added
- **双模型并发**：wan2.6-image + qwen-image-2.0-pro 同时生成
- **直接图生图**：参考图模式直接使用参考图作为输入
- 每次生成两张图片（每个模型一张）
- 发送时标注模型名称

### 🗑️ Removed
- **移除 image_analyzer.py** - 不再分析参考图
- 不再提取参考图 prompt

### 🔧 Technical Details
- 重写 `selfie.py` 支持双模型并发
- `generate_images_dual_model()` - 双模型并发生成
- `generate_single_image()` - 单模型生成
- `generate_from_reference()` - 参考图模式（直接图生图）
- 使用 ThreadPoolExecutor 并发
- wan2.6-image: 2K 分辨率
- qwen-image-2.0-pro: 1024*1024 分辨率

---

## [3.8.0] - 2026-03-30

### ✨ Added
- **增强图片真实感**：添加自然皮肤纹理、毛孔细节、真实光影等标签
- **减少 AI 感**：去除"高级滤镜"、"ins 风"等过度美化标签
- **关闭 PROMPT_EXTEND**：避免 AI 自动扩展导致过度美化

### 🔧 Technical Details
- 修改 `build_prompt()` 函数
- 增加"真实摄影"、"胶片质感"、"生活照风格"等标签
- `PROMPT_EXTEND = False`

---

## [3.7.1] - 2026-03-30

### 🐛 Fixed
- **image_analyzer.py 导入问题**：修复 `dashscope` 变量未定义错误
- 将 `import dashscope` 移到函数开头，避免作用域问题

### 📦 Technical Details
- 图片分析模块导入顺序优化
- 确保首次使用参考图功能时正常工作

---

## [3.7.0] - 2026-03-30

### ✨ Added
- **参考图生成功能**：支持分析参考图并生成模仿图
- **图片分析模块**：新增 `image_analyzer.py`，使用 qwen3.5-plus 视觉能力
- **Prompt 提取**：自动提取场景、穿搭、妆容、姿势、光线等详细 prompt
- **关键词检测**：支持"模仿"、"参考"、"类似"、"照着"、"按照"、"学"、"同款"等

### 🔧 Technical Details
- 图片分析：qwen3.5-plus 多模态模型
- 图生图：wan2.6-image 模型
- 新增 `generate_from_reference()` 函数
- aevia.sh 支持 `AEVIA_IMAGE_PATH` 环境变量

### 📦 文件变更
- `scripts/image_analyzer.py` (新增)
- `scripts/selfie.py` (修改)
- `scripts/aevia.sh` (修改)

---

## [3.6.1] - 2026-03-30

### 🐛 Fixed
- **飞书图片上传参数错误**：添加 `image_type=message` 参数
- **错误码 234001**：修复 Invalid request param 问题

### 🔧 Technical Details
- 飞书 API `/im/v1/images` 必须指定 `image_type=message`
- 确保原生图片上传功能正常工作

---

## [3.6.0] - 2026-03-30

### ✨ Added
- **网红风格 Prompt**：自拍生成升级为网红风格，添加精致妆容、时尚穿搭、ins 风、小红书风格等元素
- **飞书原生图片支持**：通过飞书 API 上传获取 image_key，发送原生 image 消息（非文件）
- **人设自动检测与配置**：首次使用自拍/语音功能时自动配置 SOUL.md 和 IDENTITY.md 为小柔人设
- **专业摄影标签**：8K 超高清、电影级布光、专业后期、色彩饱满

### 🔧 Optimized
- **aevia.sh 飞书凭证读取**：支持新旧两种配置格式，兼容 channels.feishu.appId 和 accounts 数组
- **自拍模式检测**：优化关键词匹配，避免与语音模式冲突
- **Python 路径修复**：统一使用 python3.11 调用 TTS 脚本
- **降级方案优化**：飞书原生格式失败时自动降级为文件发送

### 📦 Technical Details
- ✅ 新增 `get_feishu_credentials()` 获取飞书 API 凭证
- ✅ 新增 `upload_feishu_image()` 上传图片获取 image_key
- ✅ 新增 `send_feishu_image_message()` 发送原生图片消息
- ✅ 新增 `check_and_setup_persona()` 自动检测并配置人设
- ✅ 零敏感信息提交，配置可移植

---

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
