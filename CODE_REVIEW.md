# 小柔 AI (xiaorou) 项目 Code Review 报告

**审查日期**: 2026-03-21  
**审查人**: AI Code Review Agent  
**项目地址**: https://github.com/OMclaw/xiaorou  
**审查范围**: 安全性、架构设计、代码优雅性

---

## 📊 整体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 🔒 安全性 | ⚠️ 5/10 | 存在多处安全隐患，需优先修复 |
| 🏗️ 架构设计 | ⚠️ 6/10 | 结构基本合理，但存在依赖缺失和模块耦合问题 |
| ✨ 代码优雅性 | ⚠️ 6/10 | 可读性尚可，但注释不足、错误处理不完善 |
| **综合评分** | **⚠️ 5.7/10** | **需要重点改进，尤其是安全性方面** |

---

## 🔴 P0 严重问题（必须立即修复）

### P0-1: API Key 硬编码风险 - 脚本中直接暴露密钥

**位置**: `scripts/aevia.sh` (第 12-18 行), `scripts/selfie.py` (第 14 行), `scripts/character.sh` (第 12-16 行)

**问题描述**: 
- API Key 通过环境变量传递，但在脚本中直接使用，存在日志泄露风险
- 错误消息会提示用户将 API Key 放在 `~/.openclaw/openclaw.json`，但该文件权限未验证
- `selfie.py` 中使用 `os.environ.get()` 获取密钥，未做安全校验

**风险**: 
- 如果脚本执行日志被记录，API Key 可能泄露
- 多用户环境下，openclaw.json 可能被其他用户读取

**修复建议**:
1. 使用更安全的方式读取配置文件（限制文件权限）
2. 避免在错误消息中暴露配置路径
3. 添加 API Key 格式验证

**修复前**:
```bash
# scripts/aevia.sh
if [ -z "$DASHSCOPE_API_KEY" ]; then
  if [ -f "$HOME/.openclaw/openclaw.json" ]; then
    export DASHSCOPE_API_KEY=$(cat "$HOME/.openclaw/openclaw.json" | jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' | head -1)
  fi
fi

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY"
  echo "   在 ~/.openclaw/openclaw.json 中配置"
  exit 1
fi
```

**修复后**:
```bash
# scripts/aevia.sh
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

# 安全读取配置
load_api_key() {
  if [ -n "$DASHSCOPE_API_KEY" ]; then
    return 0
  fi
  
  if [ -f "$CONFIG_FILE" ]; then
    # 检查文件权限（仅所有者可读写）
    local perms=$(stat -c %a "$CONFIG_FILE" 2>/dev/null || stat -f %Lp "$CONFIG_FILE" 2>/dev/null)
    if [ "$perms" != "600" ] && [ "$perms" != "400" ]; then
      echo "⚠️ 警告：配置文件权限不安全，建议运行：chmod 600 $CONFIG_FILE" >&2
    fi
    
    local key=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$CONFIG_FILE" 2>/dev/null | head -1)
    if [ -n "$key" ] && [[ "$key" =~ ^sk-[a-zA-Z0-9]{20,} ]]; then
      export DASHSCOPE_API_KEY="$key"
      return 0
    fi
  fi
  
  return 1
}

if ! load_api_key; then
  echo "❌ 无法加载 API Key，请检查配置" >&2
  exit 1
fi

# 隐藏 API Key（避免在日志中暴露）
set +x
```

---

### P0-2: 用户输入未验证 - 命令注入风险

**位置**: `scripts/aevia.sh` (第 26-27 行，第 33 行), `scripts/character.sh` (第 18 行)

**问题描述**:
- 用户输入 `$USER_INPUT` 直接用于 `grep` 和 `curl` 请求
- 未对输入进行任何 sanitization 或长度限制
- 可能遭受命令注入或 prompt injection 攻击

**风险**:
- 恶意用户可注入特殊字符执行任意命令
- Prompt injection 可能导致 AI 执行非预期操作

**修复建议**:
1. 对用户输入进行长度限制
2. 过滤危险字符
3. 使用参数化方式传递数据

**修复前**:
```bash
USER_INPUT="$1"
CHANNEL="$2"

if echo "$USER_INPUT" | grep -qiE "(照片 | 图片 | 自拍 | 发张 | 看看你 | 穿 | 穿搭 | 全身 | 镜子|pic|photo|selfie)"; then
  echo "📸 自拍模式"
  python3 "$SCRIPT_DIR/selfie.py" "$USER_INPUT" "$CHANNEL" "给你看看我现在的样子~"
fi
```

**修复后**:
```bash
# 输入验证函数
sanitize_input() {
  local input="$1"
  local max_len=500
  
  # 长度限制
  if [ ${#input} -gt $max_len ]; then
    echo "⚠️ 输入过长，已截断" >&2
    input="${input:0:$max_len}"
  fi
  
  # 移除危险字符（保留中文和常见标点）
  input=$(echo "$input" | tr -d '\000-\011\013-\037\177' | sed 's/[`$(){};|&!]//g')
  
  echo "$input"
}

USER_INPUT_RAW="$1"
CHANNEL="$2"

# 验证和清理输入
if [ -z "$USER_INPUT_RAW" ]; then
  echo "用法：$0 <消息> [频道]" >&2
  exit 1
fi

USER_INPUT=$(sanitize_input "$USER_INPUT_RAW")

# 验证频道参数（白名单）
validate_channel() {
  local channel="$1"
  case "$channel" in
    feishu|telegram|discord|whatsapp|"")
      echo "$channel"
      ;;
    *)
      echo "⚠️ 未知频道：$channel，忽略" >&2
      echo ""
      ;;
  esac
}

CHANNEL=$(validate_channel "$CHANNEL")
```

---

### P0-3: 文件路径遍历风险

**位置**: `scripts/selfie.py` (第 17-18 行)

**问题描述**:
- `DEFAULT_CHARACTER_PATH` 直接使用相对路径拼接
- 未验证文件是否在预期目录内
- 如果 `assets/default-character.png` 被替换为恶意文件，可能导致安全问题

**风险**:
- 目录遍历攻击
- 恶意文件执行

**修复建议**:
```python
# scripts/selfie.py
from pathlib import Path
import os

def safe_resolve_path(base_dir: Path, relative_path: str) -> Path:
    """安全地解析路径，防止目录遍历"""
    # 解析绝对路径
    resolved = (base_dir / relative_path).resolve()
    
    # 确保路径在基目录内
    try:
        resolved.relative_to(base_dir.resolve())
        return resolved
    except ValueError:
        raise ValueError(f"路径超出允许范围：{relative_path}")

# 使用
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CHARACTER_PATH = safe_resolve_path(PROJECT_ROOT, 'assets/default-character.png')

# 验证文件存在且为普通文件
if not DEFAULT_CHARACTER_PATH.exists():
    print(f"❌ 未找到头像文件")
    sys.exit(1)

if not DEFAULT_CHARACTER_PATH.is_file():
    print(f"❌ 头像路径不是有效文件")
    sys.exit(1)

# 检查文件权限
file_stat = DEFAULT_CHARACTER_PATH.stat()
if file_stat.st_mode & 0o022:  # 其他人可写
    print(f"⚠️ 警告：头像文件权限过于开放")
```

---

## 🟠 P1 重要问题（建议尽快修复）

### P1-1: 依赖文件缺失

**位置**: `scripts/character.sh` (第 12 行)

**问题描述**:
```bash
source "$SCRIPT_DIR/../load_config.sh" 2>/dev/null || true
```
- `load_config.sh` 文件在仓库中不存在（404）
- 使用 `|| true` 静默失败，导致后续逻辑可能异常

**风险**: 配置加载失败时行为不明确

**修复建议**:
1. 创建 `load_config.sh` 文件，或
2. 移除对该文件的依赖，统一配置加载逻辑

**修复方案**:
```bash
# 方案 A: 创建 load_config.sh
cat > scripts/load_config.sh << 'EOF'
#!/bin/bash
# load_config.sh - 加载 OpenClaw 配置

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$DASHSCOPE_API_KEY" ] && [ -f "$HOME/.openclaw/openclaw.json" ]; then
  export DASHSCOPE_API_KEY=$(jq -r '.skills.entries[]?.env?.DASHSCOPE_API_KEY // empty' "$HOME/.openclaw/openclaw.json" 2>/dev/null | head -1)
fi

if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "❌ 请设置 DASHSCOPE_API_KEY 环境变量" >&2
  return 1
fi

return 0
EOF
chmod +x scripts/load_config.sh

# 方案 B: 移除依赖，直接在 character.sh 中加载配置（推荐）
```

---

### P1-2: 错误处理不完善

**位置**: 所有脚本文件

**问题描述**:
- 错误消息输出到 stdout 而非 stderr
- 退出码不统一（有时用 `exit 1`，有时未指定）
- 未记录错误日志

**修复建议**:
```bash
# 统一错误处理
error() {
  echo "❌ 错误: $*" >&2
  exit 1
}

warn() {
  echo "⚠️ 警告: $*" >&2
}

info() {
  echo "ℹ️  $*"
}

# 使用示例
if [ ! -f "$CONFIG_FILE" ]; then
  error "配置文件不存在"
fi
```

```python
# Python 脚本中使用 logging 模块
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger(__name__)

# 使用
logger.error("生成失败")
logger.warning("配置缺失")
logger.info("处理完成")
```

---

### P1-3: 安装脚本权限问题

**位置**: `install.sh` (第 19-49 行), `install-aevia.sh`

**问题描述**:
- 安装脚本会覆盖 `SOUL.md` 和 `IDENTITY.md`
- 未备份原有文件
- 未验证写入权限

**风险**: 用户自定义配置被意外覆盖

**修复建议**:
```bash
# install.sh
SOUL_FILE="$WORKSPACE_DIR/SOUL.md"
IDENTITY_FILE="$WORKSPACE_DIR/IDENTITY.md"

# 备份现有文件
backup_file() {
  local file="$1"
  if [ -f "$file" ]; then
    local backup="${file}.backup.$(date +%Y%m%d%H%M%S)"
    cp "$file" "$backup"
    echo "📦 已备份：$backup"
  fi
}

backup_file "$SOUL_FILE"
backup_file "$IDENTITY_FILE"

# 询问是否覆盖
if [ -f "$SOUL_FILE" ]; then
  read -p "⚠️  $SOUL_FILE 已存在，是否覆盖？[y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "⏭️  跳过 SOUL.md"
    SOUL_FILE=""
  fi
fi
```

---

### P1-4: 敏感信息可能泄露到日志

**位置**: `scripts/aevia.sh` (第 35-45 行)

**问题描述**:
- curl 请求的完整 JSON 包含在脚本中
- 如果启用 bash -x 调试模式，API Key 会暴露

**修复建议**:
```bash
# 禁用调试模式下的敏感信息输出
set +x  # 在读取 API Key 后禁用

# 使用 --silent 和 --fail 选项
RESPONSE=$(curl -s -f -X POST "$API_URL" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON_FILE")  # 使用临时文件而非内联 JSON

# 清理临时文件
trap "rm -f $TEMP_JSON_FILE" EXIT
```

---

## 🟡 P2 次要问题（建议改进）

### P2-1: 项目结构不完整

**位置**: 项目根目录

**问题描述**:
- 缺少 `.gitignore` 文件
- 缺少 `LICENSE` 文件
- 缺少 `requirements.txt` (Python 依赖)
- `selfie.py` 依赖 `requests` 但未声明

**修复建议**:
```bash
# 创建 .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.env
.venv/

# 配置文件
openclaw.json
*.backup.*

# 生成文件
assets/*.png
!assets/default-character.png

# 日志
*.log

# 系统文件
.DS_Store
Thumbs.db
EOF

# 创建 requirements.txt
cat > requirements.txt << 'EOF'
dashscope>=1.14.0
requests>=2.28.0
EOF

# 创建 LICENSE（根据项目需求选择合适的许可证）
```

---

### P2-2: 函数/脚本过长

**位置**: `scripts/selfie.py` (第 27-108 行)

**问题描述**:
- `generate_selfie` 函数超过 80 行
- 混合了多个职责（验证、API 调用、文件处理、消息发送）

**修复建议**:
```python
def generate_selfie(context, caption="给你看看我现在的样子~", channel=None):
    """主入口函数"""
    validate_config()
    image_path = validate_character_image()
    mode, prompt = build_prompt(context)
    image_url = call_image_api(image_path, prompt)
    if channel:
        send_to_channel(image_url, caption, channel)
    return image_url

def validate_config():
    """验证配置"""
    if not DASHSCOPE_API_KEY:
        raise ConfigurationError("API Key 未设置")

def validate_character_image():
    """验证头像文件"""
    if not DEFAULT_CHARACTER_PATH.exists():
        raise FileNotFoundError("头像文件不存在")
    return DEFAULT_CHARACTER_PATH

def build_prompt(context):
    """构建提示词"""
    if any(kw in context.lower() for kw in ['穿', '衣服', '穿搭', '全身', '镜子']):
        return "mirror", f"在对镜自拍，{context}，全身照，镜子反射，自然光线，真实感，高清"
    else:
        return "direct", f"{context}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"

def call_image_api(image_path, prompt):
    """调用图像生成 API"""
    # ... API 调用逻辑
    pass

def send_to_channel(image_url, caption, channel):
    """发送到频道"""
    # ... 消息发送逻辑
    pass
```

---

### P2-3: 注释不足

**位置**: 所有文件

**问题描述**:
- 缺少文件级文档字符串
- 复杂逻辑无注释
- 魔法数字无解释

**修复建议**:
```python
#!/usr/bin/env python3
"""
selfie.py - 自拍生成模块

基于小柔头像的图生图功能，使用 Wan2.6-image 模型生成各种场景的自拍照片。

功能:
    - 根据场景描述生成自拍
    - 支持对镜自拍和直接自拍两种模式
    - 自动发送到指定频道

使用示例:
    python3 selfie.py "在咖啡厅喝咖啡" feishu "给你看看我现在的样子~"

依赖:
    - dashscope: 阿里云百炼 SDK
    - requests: HTTP 请求库
"""

# 配置常量
DEFAULT_IMAGE_SIZE = "2K"  # 最高分辨率
DEFAULT_WATERMARK = False  # 不加水印
PROMPT_EXTEND = True  # 自动优化提示词
```

---

### P2-4: 命名规范不一致

**位置**: 所有文件

**问题描述**:
- Shell 脚本使用 `SCREAMING_SNAKE_CASE` (如 `USER_INPUT`)
- Python 脚本混用 `snake_case` 和 `CamelCase`
- 变量名有时过于简略

**修复建议**:
```bash
# Shell 脚本：使用小写 + 下划线
user_input="$1"
channel="$2"
config_file="$HOME/.openclaw/openclaw.json"

# Python 脚本：遵循 PEP 8
character_name = os.environ.get('AEVIA_CHARACTER_NAME', '小柔')
default_character_path = SCRIPT_DIR.parent / 'assets' / 'default-character.png'
```

---

## 🟢 P3 轻微问题（可选改进）

### P3-1: 缺少单元测试

**问题描述**: 项目无任何测试文件

**建议**:
```bash
# 创建 tests/ 目录
tests/
├── test_aevia.sh
├── test_selfie.py
└── test_character.sh
```

---

### P3-2: 缺少使用示例和文档

**问题描述**: 
- README.md 示例较简单
- 缺少故障排查指南
- 缺少 API 参考文档

**建议**: 添加 `docs/` 目录，包含：
- 详细使用指南
- 常见问题解答
- API 参考

---

### P3-3: 硬编码字符串

**位置**: `scripts/aevia.sh` (第 36 行)

**问题描述**:
```bash
echo "📸 自拍模式"
```
- UI 文本硬编码在代码中
- 不利于国际化

**建议**: 提取到配置文件
```bash
# config/messages.sh
MSG_SELFIE_MODE="📸 自拍模式"
MSG_CHAT_MODE="💬 聊天模式"
MSG_ERROR_API_KEY="❌ 无法加载 API Key"
```

---

## 📋 架构审查总结

### 优点
1. ✅ 项目结构清晰，功能模块化
2. ✅ Shell + Python 混合使用合理（Shell 做流程控制，Python 处理复杂逻辑）
3. ✅ 支持多平台（飞书/Telegram/Discord/WhatsApp）
4. ✅ 自动配置加载，用户体验好

### 缺点
1. ❌ 模块间耦合度高（selfie.py 直接调用 openclaw CLI）
2. ❌ 缺少配置管理模块
3. ❌ 错误处理不统一
4. ❌ 缺少日志系统

### 架构改进建议

```
xiaorou/
├── config/
│   ├── __init__.py
│   └── loader.py        # 统一配置加载
├── core/
│   ├── __init__.py
│   ├── chat.py          # 聊天逻辑
│   ├── selfie.py        # 自拍生成
│   └── character.py     # 角色生成
├── utils/
│   ├── __init__.py
│   ├── validators.py    # 输入验证
│   ├── security.py      # 安全工具
│   └── logger.py        # 日志系统
├── scripts/
│   ├── aevia.sh
│   ├── character.sh
│   └── load_config.sh
├── tests/
├── docs/
├── assets/
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## 🔧 优先级修复清单

| 优先级 | 问题 | 预计工时 | 状态 |
|--------|------|----------|------|
| P0 | API Key 安全处理 | 2h | 🔴 待修复 |
| P0 | 用户输入验证 | 1h | 🔴 待修复 |
| P0 | 文件路径安全 | 1h | 🔴 待修复 |
| P1 | 创建 load_config.sh | 0.5h | 🟠 待修复 |
| P1 | 统一错误处理 | 1h | 🟠 待修复 |
| P1 | 安装脚本改进 | 1h | 🟠 待修复 |
| P2 | 添加 .gitignore | 0.5h | 🟡 待修复 |
| P2 | 创建 requirements.txt | 0.5h | 🟡 待修复 |
| P2 | 代码重构（函数拆分） | 3h | 🟡 待修复 |
| P2 | 补充注释和文档 | 2h | 🟡 待修复 |
| P3 | 添加单元测试 | 4h | 🟢 可选 |
| P3 | 国际化支持 | 2h | 🟢 可选 |

**总预计工时**: ~18 小时

---

## 📝 整体改进建议

### 短期（1-2 周）
1. **优先修复所有 P0 安全问题**
2. 创建缺失的配置文件（.gitignore, requirements.txt, LICENSE）
3. 统一错误处理和日志输出

### 中期（1 个月）
1. 重构代码结构，拆分大函数
2. 添加配置管理模块
3. 补充文档和注释
4. 添加基础单元测试

### 长期（3 个月）
1. 实现完整的日志系统
2. 添加国际化支持
3. 性能优化（缓存、并发）
4. 添加更多自拍模式和场景

---

## 🎯 结论

小柔 AI 项目功能完整、创意良好，但在**安全性**和**代码质量**方面存在明显不足。建议优先修复 P0 级别的安全问题，再进行架构优化和代码重构。

**推荐修复顺序**:
1. 🔒 安全性修复（P0）
2. 🏗️ 基础架构完善（P1）
3. ✨ 代码质量提升（P2）
4. 📚 文档和测试（P3）

---

*报告生成时间：2026-03-21*  
*审查工具：AI Code Review Agent*
