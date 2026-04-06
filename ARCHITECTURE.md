# 小柔 AI - 三种生图模式架构说明

**版本**: v4.6.0  
**更新日期**: 2026-04-06

---

## 📸 三种生图模式定位

| 模式 | 脚本 | 并发模型 | 生成数量 | 用途 |
|------|------|----------|----------|------|
| **场景生图** | `selfie.py` | 1 个 | 1 张 | 根据文字描述生成场景 |
| **参考生图** | `selfie.py` | 2 个 | 2 张 | 分析参考图后生成 |
| **换脸生图** | `face_swap.py` | 4 个 | 4 张 | 精准换脸 |

---

## 1️⃣ 场景生图 (Scene Selfie)

**文件**: `scripts/selfie.py`

**生成配置**:
- **模型**: wan2.7-image 或 qwen-image-2.0-pro
- **数量**: 1 张图
- **输入**: 文字场景描述 + 小柔默认头像

**使用方式**:
```bash
# 通过 aevia.sh
bash scripts/aevia.sh "发张自拍，在海边看日落" feishu

# 直接调用
python3 scripts/selfie.py "时尚穿搭，自然微笑" feishu "配文" "ou_xxx"
```

**关键词**:
- 发张自拍、想要一张、生成一张、来一张
- 穿、穿搭、在...里/前/下

---

## 2️⃣ 参考生图 (Reference Selfie)

**文件**: `scripts/selfie.py --reference`

**生成配置**:
- **模型**: wan2.7-image + qwen-image-2.0-pro
- **数量**: 2 张图（双模型并发）
- **输入**: 参考图 + 小柔默认头像

**流程**:
1. 调用 `image_analyzer.py` 分析参考图
2. 提取场景、姿势、服装、光线等描述（忽略人脸）
3. 使用小柔头像作为图生图输入
4. 双模型并发生成
5. 发送 2 张图片

**使用方式**:
```bash
# 通过 aevia.sh（发送图片 + 说"参考这张图"）
bash scripts/aevia.sh --selfie-reference "参考这张图" feishu

# 直接调用
python3 scripts/selfie.py --reference /path/to/reference.jpg feishu "配文" "ou_xxx"
```

**关键词**:
- 参考、模仿、照着、学这张
- 类似的、同样的、照这个、按这个

---

## 3️⃣ 换脸生图 (Face Swap)

**文件**: `scripts/face_swap.py`

**生成配置**:
- **模型**: wan2.7-image, wan2.7-image-pro, qwen-image-2.0, qwen-image-2.0-pro
- **数量**: 4 张图（4 模型并发）
- **输入**: 用户图片（图 1）+ 小柔默认头像（图 2）

**流程**:
1. 验证用户图片和小柔头像
2. 调用 `image_analyzer.py` 分析目标图场景（不含脸部）
3. 生成精准换脸 Prompt（脸部锁定指令）
4. 4 模型并发生成
5. 自动发送到指定频道

**使用方式**:
```bash
# 通过 aevia.sh（发送图片 + 说"换脸"）
bash scripts/aevia.sh --face-swap "换脸" feishu

# 直接调用（推荐）
python3 scripts/face_swap.py /path/to/image.jpg \
  --channel feishu \
  --target "ou_xxx" \
  --caption "换脸完成～"

# 指定模型
python3 scripts/face_swap.py /path/to/image.jpg \
  --models wan2.7-image wan2.7-image-pro \
  --channel feishu \
  --target "ou_xxx"
```

**关键词**:
- 换脸、换我的脸、把脸换成、用我的脸
- face swap

---

## 🔧 技术细节

### 模型配置

**wan2.7-image 系列**:
- Size 参数格式：`"1K"`
- 分辨率：约 1024x1024

**qwen-image-2.0 系列**:
- Size 参数格式：`"1024*1024"`
- 分辨率：1024x1024

### 并发策略

| 模式 | 并发数 | 理由 |
|------|--------|------|
| 场景生图 | 1 | 简单场景描述，单模型足够 |
| 参考生图 | 2 | 需要不同风格对比 |
| 换脸生图 | 4 | 换脸难度高，多模型提高成功率 |

### 代码清理

**删除的重复功能**:
- ❌ `selfie.py` 中的 `generate_face_swap()` 函数
- ❌ `selfie.py --face-swap` 命令行参数
- ❌ 换脸功能的重复实现

**统一的入口**:
- ✅ 换脸生图统一使用 `face_swap.py`
- ✅ 场景/参考生图使用 `selfie.py`
- ✅ 自然语言入口统一使用 `aevia.sh`

---

## 📊 性能对比

| 指标 | 场景生图 | 参考生图 | 换脸生图 |
|------|----------|----------|----------|
| 生成时间 | ~30 秒 | ~60 秒 | ~90 秒 |
| API 调用 | 1 次 | 2 次 | 4 次 |
| 成功率 | ~95% | ~90% | ~85% |
| 输出图片 | 1 张 | 2 张 | 4 张 |

---

## 🎯 最佳实践

### 场景生图
✅ 适合：明确的场景描述  
❌ 不适合：需要参考特定风格

### 参考生图
✅ 适合：模仿特定场景、穿搭、姿势  
❌ 不适合：需要换脸

### 换脸生图
✅ 适合：精准换脸、保留用户场景  
❌ 不适合：只需要场景模仿

---

## 📝 更新日志

### v4.6.0 (2026-04-06)
- ✅ 明确三种生图模式的定位和并发数量
- ✅ 删除 `selfie.py` 中的换脸功能（重复代码）
- ✅ `face_swap.py` 添加发送功能
- ✅ 更新 `aevia.sh` 换脸模式调用
- ✅ 完善文档说明

---

_小柔 AI - 让 AI 更有温度，让陪伴更真实 🦞❤️_
