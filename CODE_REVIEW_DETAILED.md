# 🔍 Aevia Virtual Companion 代码审查报告

**项目名称**: aevia-virtual-companion  
**审查日期**: 2026-03-17  
**审查范围**: 所有 .sh 和 .py 脚本  
**审查人**: AI Code Reviewer

---

## 📊 审查概览

| 文件 | 严重问题 | 中等问题 | 轻微问题 |
|------|---------|---------|---------|
| `install.sh` | 0 | 1 | 2 |
| `install-aevia.sh` | 1 | 1 | 1 |
| `scripts/sync_identity.sh` | 1 | 2 | 1 |
| `scripts/load_openclaw_config.sh` | 0 | 1 | 2 |
| `scripts/character.sh` | 1 | 2 | 2 |
| `scripts/aevia.sh` | 0 | 2 | 2 |
| `scripts/wan26_selfie.py` | 0 | 1 | 2 |
| `scripts/selfie.sh` | 1 | 2 | 1 |
| `scripts/chat.sh` | 0 | 1 | 1 |
| **总计** | **3** | **13** | **14** |

---

## 🔴 严重问题（必须修复）

### 1. `install-aevia.sh` - 管道执行远程脚本风险

**位置**: 第 3 行注释及典型用法
```bash
# curl -sSL https://raw.githubusercontent.com/OMclaw/aevia-virtual-companion/main/install-aevia.sh | bash
```

**问题描述**: 
- 从远程 URL 直接下载并执行脚本是高危操作
- 如果 GitHub 仓库被攻陷或 DNS 被劫持，攻击者可注入恶意代码
- 无法验证脚本完整性和来源真实性

**风险等级**: 🔴 严重

**修复建议**:
```bash
# 方案 1: 先下载验证再执行
curl -sSL -o /tmp/install-aevia.sh https://raw.githubusercontent.com/...
sha256sum -c checksum.txt && bash /tmp/install-aevia.sh

# 方案 2: 使用 git clone 后本地执行
git clone https://github.com/OMclaw/aevia-virtual-companion.git
cd aevia-virtual-companion && bash install-aevia.sh
```

---

### 2. `scripts/sync_identity.sh` - sed 注入风险

**位置**: 第 18-19 行
```bash
CHARACTER_NAME_ESCAPED=$(printf '%s\n' "$CHARACTER_NAME" | sed 's/[&/\]/\\&/g')
```

**问题描述**:
- 虽然有转义处理，但转义规则不完整
- 未处理 `!`、`$`、`` ` ``、`\` 等特殊字符
- 在 bash 中使用时仍可能导致命令注入
- 如果角色名包含 `$(rm -rf /)` 等恶意内容，可能被执行

**风险等级**: 🔴 严重

**修复建议**:
```bash
# 使用更严格的白名单验证
if [[ ! "$CHARACTER_NAME" =~ ^[a-zA-Z0-9\u4e00-\u9fa5_-]+$ ]]; then
  echo "❌ Error: Invalid character name format"
  exit 1
fi

# 使用 jq 进行安全的字符串处理
CHARACTER_NAME_ESCAPED=$(printf '%s' "$CHARACTER_NAME" | jq -Rs '.')
```

---

### 3. `scripts/character.sh` - API Key 直接暴露在命令行

**位置**: 第 65-70 行
```bash
RESPONSE=$(curl -s -X POST "https://dashscope.aliyuncs.com/..." \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  ...
```

**问题描述**:
- API Key 以明文形式传递给 curl 命令
- 在 `ps aux` 或 `/proc/[pid]/cmdline` 中可见
- 如果系统被入侵，攻击者可轻易获取 API Key
- 错误日志可能泄露 API Key

**风险等级**: 🔴 严重

**修复建议**:
```bash
# 使用 netrc 文件或环境变量
echo "machine dashscope.aliyuncs.com login Bearer password $DASHSCOPE_API_KEY" > ~/.netrc
chmod 600 ~/.netrc

# 或使用 curl 的配置文件
curl --config <(echo "header = \"Authorization: Bearer $DASHSCOPE_API_KEY\"") ...
```

---

### 4. `scripts/selfie.sh` - 路径遍历漏洞

**位置**: 第 43-55 行
```bash
REAL_PATH=$(realpath -m "$REFERENCE_IMAGE" 2>/dev/null || echo "")
REAL_ASSETS=$(realpath -m "$ASSETS_DIR" 2>/dev/null || echo "")

if [[ "$REAL_PATH" == "$REAL_ASSETS"/* ]] || [[ "$REFERENCE_IMAGE" == /* ]]; then
  REF_IMAGE="$REFERENCE_IMAGE"
```

**问题描述**:
- 虽然使用了 realpath 检查，但逻辑存在缺陷
- 允许绝对路径 (`[[ "$REFERENCE_IMAGE" == /* ]]`) 可能导致访问任意文件
- 攻击者可传入 `/etc/passwd` 等系统文件作为参考图像

**风险等级**: 🔴 严重

**修复建议**:
```bash
# 严格限制文件访问范围
if [[ "$REAL_PATH" != "$REAL_ASSETS"/* ]]; then
  echo "❌ Error: Reference image must be within assets directory"
  exit 1
fi

# 额外验证文件类型
if ! file "$REF_IMAGE" | grep -qE "image|PNG|JPEG"; then
  echo "❌ Error: Invalid image file"
  exit 1
fi
```

---

## 🟡 中等问题（建议修复）

### 1. `install.sh` - 备份文件权限未设置

**位置**: 第 35、52 行
```bash
cp "$SOUL_FILE" "${SOUL_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
```

**问题**: 备份文件继承原文件权限，可能过于宽松

**建议**:
```bash
cp "$SOUL_FILE" "${SOUL_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
chmod 600 "${SOUL_FILE}.backup.$(date +%Y%m%d_%H%M%S_%N)"
```

---

### 2. `install-aevia.sh` - 未验证 git 仓库完整性

**位置**: 第 24-28 行
```bash
git clone https://github.com/OMclaw/aevia-virtual-companion.git
```

**问题**: 未使用 SSH 签名验证或 commit hash 固定

**建议**:
```bash
# 固定到特定 commit hash
git clone https://github.com/OMclaw/aevia-virtual-companion.git
cd aevia-virtual-companion
git checkout <known-good-commit-hash>
```

---

### 3. `scripts/sync_identity.sh` - 错误处理不完整

**位置**: 第 36-40 行
```bash
if grep -q "^\*\*中文名\*\*:" "$SOUL_FILE" 2>/dev/null; then
  sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$SOUL_FILE"
else
  sed -i "s/^\*\*Name\*\*: .*/\*\*Name\*\*: $CHARACTER_NAME_ESCAPED\n- \*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$SOUL_FILE"
fi
```

**问题**: sed 命令失败时没有错误处理，可能静默失败

**建议**:
```bash
if ! sed -i "s/^\*\*中文名\*\*: .*/\*\*中文名\*\*: $CHARACTER_NAME_ESCAPED/" "$SOUL_FILE" 2>/dev/null; then
  echo "❌ Error: Failed to update SOUL.md"
  # 恢复备份
  cp "${SOUL_FILE}.backup."* "$SOUL_FILE"
  exit 1
fi
```

---

### 4. `scripts/load_openclaw_config.sh` - API Key 验证不充分

**位置**: 第 26-28 行
```bash
if [[ ! "$api_key" =~ ^sk-[a-zA-Z0-9_-]+$ ]]; then
  echo "⚠️  Warning: API Key format may be invalid"
fi
```

**问题**: 仅警告不阻止，可能导致后续操作失败

**建议**:
```bash
if [[ ! "$api_key" =~ ^sk-[a-zA-Z0-9_-]{20,}$ ]]; then
  echo "❌ Error: Invalid API Key format"
  return 1
fi
```

---

### 5. `scripts/character.sh` - 缺少超时控制

**位置**: 第 65 行
```bash
RESPONSE=$(curl -s -X POST ...)
```

**问题**: curl 没有设置超时，可能无限期挂起

**建议**:
```bash
RESPONSE=$(curl -s --max-time 60 --connect-timeout 10 -X POST ...)
```

---

### 6. `scripts/character.sh` - 临时文件未清理

**位置**: 第 58-63 行
```bash
PAYLOAD=$(jq -n \
  --arg model "z-image-turbo" \
  ...)
```

**问题**: 如果脚本被中断，临时文件可能残留

**建议**: 使用 trap 清理
```bash
trap 'rm -f /tmp/aevia_payload_*.json 2>/dev/null' EXIT
```

---

### 7. `scripts/aevia.sh` - 输入验证不足

**位置**: 第 44-48 行
```bash
if echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | ...)"; then
  is_photo_request=true
fi
```

**问题**: 
- 使用 echo 可能触发命令替换
- 未过滤 `$()`、`` ` `` 等危险字符

**建议**:
```bash
# 使用 printf 代替 echo，并预先清理输入
SAFE_INPUT=$(printf '%s' "$USER_INPUT" | tr -d '$`\\')
if printf '%s' "$SAFE_INPUT" | grep -qiE "(...)"; then
  is_photo_request=true
fi
```

---

### 8. `scripts/aevia.sh` - 子脚本调用未验证

**位置**: 第 67、72 行
```bash
bash "$SCRIPT_DIR/selfie.sh" ...
bash "$SCRIPT_DIR/chat.sh" ...
```

**问题**: 未检查脚本是否存在及完整性

**建议**:
```bash
if [[ ! -x "$SCRIPT_DIR/selfie.sh" ]]; then
  echo "❌ Error: selfie.sh not found or not executable"
  exit 1
fi
```

---

### 9. `scripts/wan26_selfie.py` - 未验证 API 响应

**位置**: 第 113-117 行
```python
if 'code' in result and result['code'] not in [None, '']:
    sys.exit(1)
```

**问题**: 未检查 HTTP 状态码，可能忽略错误

**建议**:
```python
response.raise_for_status()  # 在 requests.post 后添加
```

---

### 10. `scripts/selfie.sh` - 重试机制可能被滥用

**位置**: 第 79-93 行
```bash
while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
```

**问题**: 
- 重试间隔太短 (2 秒)
- 可能被用来进行 DoS 攻击

**建议**:
```bash
RETRY_DELAY=$((ATTEMPT * 5))  # 指数退避
sleep $RETRY_DELAY
```

---

### 11. `scripts/selfie.sh` - 图片下载未验证

**位置**: 第 109 行
```bash
curl -s "$IMAGE_URL" -o "$OUTPUT_PATH"
```

**问题**: 未验证下载内容是否为有效图片

**建议**:
```bash
curl -s --max-time 30 "$IMAGE_URL" -o "$OUTPUT_PATH"
if ! file "$OUTPUT_PATH" | grep -qE "image|PNG|JPEG"; then
  rm -f "$OUTPUT_PATH"
  echo "❌ Error: Downloaded file is not a valid image"
  exit 1
fi
```

---

### 12. `scripts/chat.sh` - 系统提示可被注入

**位置**: 第 23-35 行
```bash
SYSTEM_PROMPT="你是${CHARACTER_NAME}，用户的虚拟伴侣。..."
```

**问题**: CHARACTER_NAME 未经验证直接拼接到提示词

**建议**:
```bash
# 清理角色名中的特殊字符
SAFE_CHAR_NAME=$(printf '%s' "$CHARACTER_NAME" | tr -d '"\n\r\\')
SYSTEM_PROMPT="你是${SAFE_CHAR_NAME}，用户的虚拟伴侣。..."
```

---

### 13. `scripts/chat.sh` - 缺少速率限制

**位置**: 第 52-58 行
```bash
RESPONSE=$(curl -s --max-time 60 --retry 2 -X POST ...)
```

**问题**: 无请求频率限制，可能触发 API 限流

**建议**: 添加简单的速率限制
```bash
# 在脚本开头添加
RATE_LIMIT_FILE="/tmp/aevia_rate_limit"
if [ -f "$RATE_LIMIT_FILE" ]; then
  LAST_REQUEST=$(cat "$RATE_LIMIT_FILE")
  NOW=$(date +%s)
  if [ $((NOW - LAST_REQUEST)) -lt 2 ]; then
    sleep 2
  fi
fi
date +%s > "$RATE_LIMIT_FILE"
```

---

## 🟢 轻微问题（可选优化）

### 1. `install.sh` - 硬编码的工作目录检测逻辑

**位置**: 第 10-17 行

**问题**: 逻辑复杂且可能出错

**建议**: 简化为单一检测点
```bash
WORKSPACE_DIR="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
```

---

### 2. `install.sh` - 缺少卸载功能

**建议**: 添加 uninstall 选项

---

### 3. `scripts/load_openclaw_config.sh` - 配置文件路径硬编码

**位置**: 第 4-5 行

**建议**: 支持 XDG 配置目录规范
```bash
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
config_paths=(
  "$HOME/.openclaw/openclaw.json"
  "$XDG_CONFIG_HOME/openclaw/config.json"
)
```

---

### 4. `scripts/character.sh` - 缺少图片尺寸验证

**建议**: 添加图片尺寸检查
```bash
if ! identify "$OUTPUT_PATH" 2>/dev/null; then
  echo "⚠️  Warning: Could not verify image dimensions"
fi
```

---

### 5. `scripts/character.sh` - 错误信息不够友好

**建议**: 提供更详细的故障排除指南

---

### 6. `scripts/aevia.sh` - 缺少日志记录

**建议**: 添加可选的日志功能
```bash
LOG_FILE="${AEVIA_LOG_FILE:-/tmp/aevia.log}"
echo "[$(date -Iseconds)] $USER_INPUT" >> "$LOG_FILE"
```

---

### 7. `scripts/aevia.sh` - 关键词匹配可能误判

**位置**: 第 44-52 行

**问题**: 正则表达式过于宽泛

**建议**: 使用更精确的匹配或意图分类

---

### 8. `scripts/wan26_selfie.py` - 缺少日志记录

**建议**: 添加 logging 模块
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

---

### 9. `scripts/wan26_selfie.py` - 未使用类型提示

**建议**: 添加 Python 类型提示提高可读性

---

### 10. `scripts/selfie.sh` - 缺少使用统计

**建议**: 添加匿名使用统计（可选）

---

### 11. `scripts/selfie.sh` - 变量命名不一致

**问题**: 混用 `REF_IMAGE`、`REFERENCE_IMAGE`

**建议**: 统一命名规范

---

### 12. `scripts/chat.sh` - 缺少对话历史支持

**建议**: 添加多轮对话上下文支持

---

### 13. `scripts/chat.sh` - 温度参数硬编码

**位置**: 第 56 行
```bash
temperature: 0.8,
```

**建议**: 允许通过环境变量配置

---

### 14. 整体 - 缺少单元测试

**建议**: 为关键函数添加测试用例

---

## ✅ 值得肯定的优点

1. **使用 `set -euo pipefail`**: 大多数脚本正确设置了严格的错误处理
2. **API Key 多来源支持**: 支持环境变量、配置文件、命令行参数多种来源
3. **重试机制**: selfie.sh 实现了 API 调用重试
4. **输入长度限制**: chat.sh 和 selfie.sh 对输入长度进行了限制
5. **路径解析**: 使用 `SCRIPT_DIR` 避免相对路径问题
6. **Python 脚本分离**: wan26_selfie.py 独立处理长参数，避免"参数列表过长"错误
7. **备份机制**: sync_identity.sh 在修改前创建带时间戳的备份

---

## 📋 修复优先级建议

### 立即修复（P0）
1. `install-aevia.sh` 远程脚本执行风险
2. `scripts/sync_identity.sh` sed 注入风险
3. `scripts/character.sh` API Key 暴露问题
4. `scripts/selfie.sh` 路径遍历漏洞

### 尽快修复（P1）
1. 所有脚本的 API Key 验证增强
2. 输入验证和清理
3. 超时控制完善
4. 错误处理改进

### 后续优化（P2）
1. 日志记录功能
2. 单元测试
3. 代码规范化
4. 文档完善

---

## 🔐 安全最佳实践建议

1. **最小权限原则**: 脚本只请求必要的权限
2. **防御性编程**: 始终验证外部输入
3. **安全默认值**: 默认配置应该是最安全的
4. **错误处理**: 失败时不泄露敏感信息
5. **依赖验证**: 使用 checksum 或签名验证外部依赖
6. **审计日志**: 记录关键操作便于追溯

---

**审查完成时间**: 2026-03-17 16:30  
**报告版本**: v1.0
