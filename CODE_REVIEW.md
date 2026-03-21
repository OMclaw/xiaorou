# 📋 Code Review 报告 - Aevia Virtual Companion

**审查时间:** 2026-03-17 14:45  
**审查范围:** aevia-virtual-companion 项目全部脚本  
**审查工具:** AI Code Review + 人工审计

---

## 🔴 严重问题（必须修复）

### 1. **[chat.sh: 45-55 行] JSON 注入风险**

**问题描述：**
```bash
PAYLOAD=$(jq -n \
  --arg model "qwen3.5-plus" \
  --arg system "$SYSTEM_PROMPT" \
  --arg user "$USER_MESSAGE" \
  '{...}'
```

虽然使用了 `jq` 进行转义，但 `SYSTEM_PROMPT` 中包含变量 `${CHARACTER_NAME}`，如果角色名包含特殊字符可能导致 JSON 解析错误。

**风险等级:** 🔴 高  
**修复建议：**
```bash
# 先替换角色名，再用 jq 处理
SYSTEM_PROMPT="你是${CHARACTER_NAME}，用户的虚拟伴侣。..."
PAYLOAD=$(jq -n \
  --argjson system "$SYSTEM_PROMPT" \
  --argjson user "$USER_MESSAGE" \
  '{...}')
```

---

### 2. **[selfie.sh: 80-95 行] Python 代码中的命令注入风险**

**问题描述：**
```python
payload = {
    'input': {
        'messages': [{
            'content': [
                {'image': f'data:image/png;base64,{img_data}'},
                {'text': '$PROMPT'}  # ← 直接插入 Shell 变量
            ]
        }]
    }
}
```

`$PROMPT` 变量直接从 Shell 传入 Python，如果包含单引号或特殊字符可能导致 Python 语法错误。

**风险等级:** 🔴 高  
**修复建议：**
```bash
# 使用环境变量传递，避免直接插入
export PROMPT="$PROMPT"
python3 - <<PYTHON
import os
prompt = os.environ.get('PROMPT', '')
# 使用 prompt 变量而不是 $PROMPT
PYTHON
```

---

### 3. **[selfie.sh: 105 行] API Key 在错误日志中可能泄露**

**问题描述：**
```bash
if echo "$RESPONSE" | jq -e '.code' > /dev/null 2>&1; then
  echo "❌ API Error: $ERROR_CODE - $ERROR_MSG"
  echo "Response: $RESPONSE"  # ← 可能包含敏感信息
fi
```

**风险等级:** 🔴 高  
**修复建议：**
```bash
# 不要在日志中打印完整响应
echo "❌ API Error: $ERROR_CODE - $ERROR_MSG"
# echo "Response: $RESPONSE"  # 注释掉或只打印非敏感部分
```

---

## 🟡 中等问题（建议修复）

### 4. **[所有脚本] 缺少网络超时和重试机制**

**问题描述：**
- `chat.sh` 有 `--max-time 30 --retry 2` ✅
- `selfie.sh` 只有 `timeout=60` 在 Python 内部 ⚠️
- `install.sh` 无任何超时设置 ❌

**风险等级:** 🟡 中  
**修复建议：**
```bash
# selfie.sh 添加 curl 超时
curl -s --connect-timeout 10 --max-time 120 --retry 3 ...

# install.sh 添加超时
curl -s --max-time 30 ... || echo "⚠️  请求超时"
```

---

### 5. **[selfie.sh: 60-70 行] 硬编码的图片路径**

**问题描述：**
```bash
if [ -n "$REFERENCE_IMAGE" ] && [ -f "$REFERENCE_IMAGE" ]; then
  REF_IMAGE="$REFERENCE_IMAGE"
elif [ -f "$SCRIPT_DIR/../assets/default-character.png" ]; then
  REF_IMAGE="$SCRIPT_DIR/../assets/default-character.png"
else
  echo "❌ Error: No reference image found"
  exit 1
fi
```

**风险等级:** 🟡 中  
**修复建议：**
```bash
# 添加更多备选路径
DEFAULT_IMAGES=(
  "$SCRIPT_DIR/../assets/default-character.png"
  "$SCRIPT_DIR/../templates/default.png"
  "/opt/openclaw/assets/default-avatar.png"
)

for img in "${DEFAULT_IMAGES[@]}"; do
  if [ -f "$img" ]; then
    REF_IMAGE="$img"
    break
  fi
done
```

---

### 6. **[aevia.sh: 35-50 行] 意图识别过于宽泛**

**问题描述：**
```bash
if echo "$USER_INPUT" | grep -qiE "照片 | 图片 | 自拍 | ... | 长什么样 | 穿 | 穿搭 | 在哪里 | 干嘛"; then
  is_photo_request=true
fi
```

"在哪里"、"干嘛" 等词可能误判为自拍请求。

**风险等级:** 🟡 中  
**修复建议：**
```bash
# 更精确的匹配
if echo "$USER_INPUT" | grep -qiE "^发张 | 自拍$|照片$|看看你 | 穿.*照片 | 发张.*自拍"; then
  is_photo_request=true
fi
```

---

### 7. **[install.sh: 25-35 行] 备份文件无清理机制**

**问题描述：**
```bash
cp "$file" "${file}.backup.$(date +%Y%m%d_%H%M%S)"
```

每次安装都会生成新备份，长期积累会占用大量空间。

**风险等级:** 🟡 中  
**修复建议：**
```bash
# 只保留最近 3 个备份
BACKUP_DIR="$(dirname "$file")"
ls -t "${file}".backup.* 2>/dev/null | tail -n +4 | xargs rm -f

# 或者限制备份数量
MAX_BACKUPS=3
backup_count=$(ls "${file}".backup.* 2>/dev/null | wc -l)
if [ $backup_count -ge $MAX_BACKUPS ]; then
  ls -t "${file}".backup.* | tail -n +$MAX_BACKUPS | xargs rm -f
fi
```

---

## 🟢 轻微问题（可选优化）

### 8. **[chat.sh: 25 行] SYSTEM_PROMPT 可以提取到配置文件**

**建议：** 将系统提示词放到 `templates/system-prompt.txt`，便于定制角色性格。

---

### 9. **[所有脚本] 缺少日志记录**

**建议：** 添加可选的日志功能，便于调试：
```bash
LOG_FILE="${LOG_FILE:-/tmp/aevia-$$.log}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$LOG_FILE"
```

---

### 10. **[install.sh] 缺少版本检查**

**建议：** 添加 OpenClaw 版本检查：
```bash
OPENCLAW_VERSION=$(openclaw --version 2>&1 | head -1)
if [[ ! "$OPENCLAW_VERSION" =~ "2026" ]]; then
  echo "⚠️  Warning: OpenClaw 版本可能过旧"
fi
```

---

### 11. **[selfie.sh: 120 行] openclaw 命令路径硬编码**

**问题描述：**
```bash
openclaw message send ...
```

**建议：** 使用 `which openclaw` 或添加路径检测：
```bash
OPENCLAW_CMD=$(which openclaw 2>/dev/null || echo "/opt/openclaw/bin/openclaw")
$OPENCLAW_CMD message send ...
```

---

## ✅ 代码亮点

1. **✅ 模块化设计优秀** - 功能分离清晰（chat/selfie/character 独立脚本）
2. **✅ 环境变量管理良好** - 无硬编码 API Key，从 OpenClaw 配置读取
3. **✅ 用户体验友好** - 详细的错误提示和使用说明
4. **✅ 自动意图识别** - 智能判断聊天/自拍请求
5. **✅ 备份机制完善** - 安装前自动备份重要文件
6. **✅ 模板化设计** - SOUL.md 使用模板覆盖，便于维护

---

## 📊 统计总结

| 严重性 | 数量 | 状态 |
|--------|------|------|
| 🔴 严重 | 3 个 | 待修复 |
| 🟡 中等 | 4 个 | 建议修复 |
| 🟢 轻微 | 4 个 | 可选优化 |
| ✅ 亮点 | 6 个 | 保持 |

---

## 🎯 修复优先级

### 第一阶段（立即修复）
1. ✅ 修复 selfie.sh 的命令注入风险
2. ✅ 移除敏感信息日志输出
3. ✅ 修复 chat.sh 的 JSON 注入风险

### 第二阶段（本周内）
4. ✅ 添加网络超时和重试机制
5. ✅ 改进图片路径检测
6. ✅ 优化意图识别逻辑

### 第三阶段（下次迭代）
7. ✅ 添加备份清理机制
8. ✅ 提取系统提示词到配置文件
9. ✅ 添加日志功能

---

## 💡 整体评价

**项目架构清晰，主要风险在安全方面。**

**优点：**
- 代码结构清晰，易于维护
- 安全意识较强（无硬编码密钥）
- 用户体验设计用心

**主要风险：**
- Shell 到 Python 的变量传递存在注入风险
- 错误日志可能泄露敏感信息
- 缺少网络超时保护

**建议：** 优先修复 3 个严重问题，然后逐步优化中等问题。整体代码质量良好，适合投入使用。

---

**审查人:** AI Code Review  
**审查日期:** 2026-03-17  
**下次审查:** 建议修复后重新审查

---

## 🔧 快速修复脚本

如果需要，可以运行以下命令自动修复部分问题：

```bash
# 1. 修复备份清理（添加到 install.sh）
cat >> /tmp/fix_install.sh << 'EOF'
# 在备份代码后添加
MAX_BACKUPS=3
for file in "$SOUL_FILE" "$IDENTITY_FILE" "$HEARTBEAT_FILE"; do
  BACKUP_DIR="$(dirname "$file")"
  ls -t "${file}".backup.* 2>/dev/null | tail -n +$MAX_BACKUPS | xargs rm -f
done
EOF

# 2. 修复日志输出（手动修改 selfie.sh 第 105 行）
sed -i 's/echo "Response: \$RESPONSE"/# echo "Response: \$RESPONSE" # 已注释，防止泄露敏感信息/' selfie.sh

# 3. 添加超时（手动修改 selfie.sh）
sed -i 's/timeout=60/timeout=60, connect_timeout=10/' selfie.sh
```

---

**让代码更安全、更健壮！** 🚀
