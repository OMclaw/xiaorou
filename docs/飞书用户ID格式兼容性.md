# 飞书用户 ID 格式兼容性说明

## 📋 支持的格式

小柔 skills 现已全面兼容所有飞书用户 ID 格式：

| 格式类型 | 示例 | 说明 |
|---------|------|------|
| **open_id** | `ou_0668d1ec503978ef15adadd736f34c46` | 最常用，推荐 |
| **带前缀的 open_id** | `user:ou_0668d1ec503978ef15adadd736f34c46` | OpenClaw 常用格式 |
| **union_id** | `on_1234567890abcdef` | 跨应用统一 ID |
| **带前缀的 union_id** | `user:on_1234567890abcdef` | - |
| **user_id** | `user_abc123` | 企业内部用户 ID |
| **带前缀的 user_id** | `user:user_abc123` | - |

## ✅ 自动处理

所有格式都会自动标准化：
- 移除 `user:` 前缀（如果有）
- 识别 ID 类型（open_id / union_id / user_id）
- 验证格式有效性

## 📝 使用示例

### 命令行调用

```bash
# 格式 1：纯 open_id（推荐）
python3 scripts/selfie_v2.py --role-swap reference.jpg feishu "配文" "ou_0668d1ec503978ef15adadd736f34c46"

# 格式 2：带前缀的 open_id
python3 scripts/selfie_v2.py --role-swap reference.jpg feishu "配文" "user:ou_0668d1ec503978ef15adadd736f34c46"

# 格式 3：union_id
python3 scripts/selfie_v2.py --role-swap reference.jpg feishu "配文" "on_1234567890abcdef"

# 格式 4：环境变量（最方便）
export AEVIA_TARGET="ou_0668d1ec503978ef15adadd736f34c46"
python3 scripts/selfie_v2.py --role-swap reference.jpg feishu "配文"
```

### 配置文件（推荐）

在 `~/.openclaw/openclaw.json` 中配置默认 target：

```json
{
  "skills": {
    "entries": {
      "xiaorou": {
        "config": {
          "feishu_target": "ou_0668d1ec503978ef15adadd736f34c46"
        }
      }
    }
  }
}
```

配置后，调用时无需每次传 target 参数。

## 🔧 核心函数

### `normalize_feishu_target()`

**位置**：`scripts/config.py`

**功能**：标准化飞书用户 ID

**返回值**：`(cleaned_id, id_type)`
- `cleaned_id`: 清理后的用户 ID（无 `user:` 前缀）
- `id_type`: `'open_id'` | `'union_id'` | `'user_id'`

**示例**：
```python
from config import normalize_feishu_target

# 示例 1：带前缀的 open_id
user_id, id_type = normalize_feishu_target("user:ou_123")
# 返回：("ou_123", "open_id")

# 示例 2：纯 union_id
user_id, id_type = normalize_feishu_target("on_abc")
# 返回：("on_abc", "union_id")
```

## 🧪 测试

运行兼容性测试：

```bash
cd /home/admin/.openclaw/workspace/skills/xiaorou
python3 scripts/test_feishu_target_compat.py
```

## 📚 受影响模块

以下模块已更新支持全格式兼容：

| 模块 | 文件 | 功能 |
|-----|------|------|
| 参考生图 | `selfie_v2.py` | ✅ 已更新 |
| BBOX 局部重绘 | `selfie_bbox.py` | ✅ 已更新 |
| 服饰修图 | `selfie_inpaint.py` | ✅ 已更新 |
| 视频生成 | `generate_video.py` | 使用 openclaw 命令，自动兼容 |
| 语音生成 | `tts.py` | 使用 openclaw 命令，自动兼容 |

## 🐛 历史问题

**问题**：2026-04-27 发现 target 参数格式不兼容

**原因**：代码只接受 `ou_xxx` 格式，不支持 `user:ou_xxx`

**修复**：
1. 添加统一的 `normalize_feishu_target()` 函数
2. 更新所有相关模块使用该函数
3. 添加完整的测试用例
4. 添加长度校验防止无效格式

**影响**：修复后，小柔 skills 可以兼容所有飞书机器人场景。

## 📖 飞书 ID 类型说明

### open_id（推荐）
- **格式**：`ou_` + 32 位字符
- **特点**：应用内唯一，最常用
- **场景**：大多数飞书应用开发场景

### union_id
- **格式**：`on_` + 字符
- **特点**：跨应用统一，同一用户在不同应用中 union_id 相同
- **场景**：多应用关联同一用户

### user_id
- **格式**：`user_` + 字符
- **特点**：企业自建应用使用
- **场景**：企业内部系统

---

**更新时间**：2026-04-27  
**版本**：小柔 AI v8.0.0
