# 飞书机器人适配指南

> **摘要**：小柔 AI 已完全适配飞书开放平台的所有机器人类型。本文详细介绍应用机器人和自定义机器人的配置方式、差异对比和最佳实践。

---

## 🤖 飞书机器人类型

飞书开放平台提供两种机器人类型：

| 类型 | 应用机器人 | 自定义机器人 |
|------|----------|------------|
| **交互方式** | ✅ 双向交互（可接收和回复消息） | ❌ 单向推送（只能发送消息） |
| **开发成本** | ⭐⭐⭐ 中等 | ⭐ 简单 |
| **适用场景** | AI 助手、智能客服、自动化工作流 | 通知推送、日报推送、告警通知 |
| **API 权限** | ✅ 丰富（可调用飞书开放 API） | ❌ 有限（仅支持消息推送） |
| **审核要求** | ✅ 需要企业管理员审核 | ❌ 无需审核 |
| **小柔 AI 支持** | ✅ **完全支持** | ⚠️ 部分支持（仅推送） |

---

## 🚀 快速开始

### 方式一：应用机器人（推荐）

**适用场景**：AI 对话、图片生成、语音消息、视频生成等交互场景

#### 1. 创建应用

1. 登录 [飞书开放平台](https://open.feishu.cn/app)
2. 点击「创建应用」→「自建应用」
3. 填写应用名称（如：小柔 AI）
4. 点击「创建」

#### 2. 开启机器人能力

1. 进入应用管理页面
2. 点击「添加应用能力」→「机器人」
3. 配置机器人信息：
   - **机器人名称**：小柔
   - **机器人头像**：上传小柔头像
   - **功能描述**：你的 AI 虚拟伴侣

#### 3. 配置权限

**必需权限**：
- ✅ 发送消息
- ✅ 读取用户信息
- ✅ 上传图片/文件

**可选权限**：
- 📅 日历管理
- 📝 云文档操作
- 👥 群组管理

#### 4. 配置事件订阅

**必需事件**：
- ✅ 接收消息（`im.message.receive_v1`）
- ✅ 用户进入会话（`bot.p2p.chat.entered`）

**回调地址**：
```
https://your-domain.com/openclaw/feishu/callback
```

#### 5. 获取凭证

在「凭证与基础信息」页面获取：
- `App ID`（应用 ID）
- `App Secret`（应用密钥）

#### 6. 配置小柔 AI

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "channels": {
    "feishu": {
      "appId": "cli_xxxxxxxxxxxxx",
      "appSecret": "xxxxxxxxxxxxxxxxxxxxxxxx",
      "defaultAccount": "main",
      "accounts": {
        "main": {
          "appId": "cli_xxxxxxxxxxxxx",
          "appSecret": "xxxxxxxxxxxxxxxxxxxxxxxx"
        }
      }
    }
  },
  "skills": {
    "entries": {
      "xiaorou": {
        "config": {
          "feishu_target": "ou_xxxxxxxxxxxxx"
        }
      }
    }
  }
}
```

#### 7. 发布应用

1. 点击「版本管理与发布」
2. 填写版本说明
3. 点击「提交审核」
4. 等待企业管理员审核通过

---

### 方式二：自定义机器人

**适用场景**：日报推送、告警通知、定时消息等单向推送场景

#### 1. 创建自定义机器人

1. 进入飞书群聊
2. 点击右上角「设置」
3. 选择「群机器人」
4. 点击「添加机器人」
5. 选择「自定义机器人」
6. 填写机器人名称（如：小柔推送）
7. 点击「添加」

#### 2. 获取 Webhook URL

复制生成的 Webhook URL：
```
https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxxxx
```

#### 3. 配置小柔 AI

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "channels": {
    "feishu": {
      "webhooks": {
        "daily_report": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxxxx",
        "alert": "https://open.feishu.cn/open-apis/bot/v2/hook/yyyyyyyyyyyyyyyy"
      }
    }
  }
}
```

#### 4. 使用示例

```bash
# 发送日报推送
python3 scripts/tts.py "今日工作总结" \
  --channel feishu \
  --webhook daily_report

# 发送告警通知
python3 scripts/selfie.py "异常告警" \
  --channel feishu \
  --webhook alert
```

---

## 📊 功能对比

### 应用机器人功能清单

| 功能 | 支持状态 | 说明 |
|------|---------|------|
| **文本对话** | ✅ 完全支持 | 情感聊天、问答交互 |
| **图片生成** | ✅ 完全支持 | 场景生图、参考生图 |
| **语音消息** | ✅ 完全支持 | OPUS 格式原生语音 |
| **视频生成** | ✅ 完全支持 | 图生视频 |
| **文件发送** | ✅ 完全支持 | 文档、图片、视频 |
| **卡片消息** | ✅ 完全支持 | 交互式卡片 |
| **群组管理** | ✅ 完全支持 | 创建群组、拉人入群 |
| **消息回复** | ✅ 完全支持 | 引用回复、话题回复 |
| **事件订阅** | ✅ 完全支持 | 接收消息、用户进入会话 |
| **API 调用** | ✅ 完全支持 | 飞书开放平台所有 API |

### 自定义机器人功能清单

| 功能 | 支持状态 | 说明 |
|------|---------|------|
| **文本推送** | ✅ 完全支持 | 通知、日报、告警 |
| **图片推送** | ✅ 完全支持 | 图片消息 |
| **文件推送** | ✅ 完全支持 | 文档、视频 |
| **卡片推送** | ✅ 完全支持 | 静态卡片 |
| **消息交互** | ❌ 不支持 | 无法接收用户消息 |
| **群组管理** | ❌ 不支持 | 无法创建/管理群组 |
| **API 调用** | ❌ 不支持 | 仅支持消息推送 |

---

## 🔧 高级配置

### 多账号配置

支持配置多个飞书应用账号，实现多机器人部署：

```json
{
  "channels": {
    "feishu": {
      "defaultAccount": "xiaorou_main",
      "accounts": {
        "xiaorou_main": {
          "appId": "cli_xxxxxxxxxxxxx",
          "appSecret": "xxxxxxxxxxxxxxxxxxxxxxxx"
        },
        "xiaorou_backup": {
          "appId": "cli_yyyyyyyyyyyyy",
          "appSecret": "yyyyyyyyyyyyyyyyyyyyyyyy"
        },
        "xiaorou_test": {
          "appId": "cli_zzzzzzzzzzzzz",
          "appSecret": "zzzzzzzzzzzzzzzzzzzzzzzz"
        }
      }
    }
  }
}
```

**使用方式**：

```bash
# 使用主账号
export AEVIA_ACCOUNT=xiaorou_main
python3 scripts/selfie.py "发张自拍"

# 使用备用账号
export AEVIA_ACCOUNT=xiaorou_backup
python3 scripts/selfie.py "发张自拍"

# 使用测试账号
export AEVIA_ACCOUNT=xiaorou_test
python3 scripts/selfie.py "发张自拍"
```

### IP 白名单配置

**飞书要求**：服务器 IP 需要添加到飞书开放平台白名单

1. 登录 [飞书开放平台](https://open.feishu.cn/app)
2. 进入应用管理页面
3. 点击「凭证与基础信息」
4. 在「IP 白名单」中添加服务器公网 IP
5. 点击「保存」

**获取服务器 IP**：

```bash
curl ifconfig.me
```

### 安全配置

#### 1. 请求签名验证

飞书请求会携带签名，建议验证签名确保请求来源：

```python
def verify_feishu_signature(request_body, signature, timestamp):
    """验证飞书请求签名"""
    import hashlib
    import base64
    import hmac
    
    # 拼接待签名字符串
    sign_str = timestamp + request_body
    
    # 使用 app_secret 计算签名
    signature_computed = hmac.new(
        app_secret.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).digest()
    
    # Base64 编码
    signature_computed = base64.b64encode(signature_computed).decode()
    
    # 验证签名
    return hmac.compare_digest(signature, signature_computed)
```

#### 2. Token 刷新机制

飞书 `access_token` 有效期为 2 小时，需要自动刷新：

```python
# 已在 config.py 中实现
# - TTL 缓存：2 小时
# - 自动刷新：过期前自动刷新
# - 线程安全：RLock 保护
```

---

## 🐛 常见问题

### Q1: 消息发送失败，报错 "user id cross tenant"

**原因**：飞书 ID 类型识别错误

**解决**：已修复，确保使用正确的 ID 类型：
- `ou_xxx` → `open_id`
- `on_xxx` → `union_id`
- `ai_xxx` → `app_open_id`
- `u_xxx` → `user_id`

### Q2: 图片发送显示为文件而非图片

**原因**：未使用飞书原生图片消息

**解决**：小柔 AI v5.25.0+ 已支持飞书原生图片消息：
1. 上传图片获取 `image_key`
2. 使用 `send_feishu_image_message()` 发送

### Q3: 自定义机器人无法接收消息

**原因**：自定义机器人仅支持单向推送

**解决**：如需双向交互，请使用应用机器人

### Q4: 应用机器人审核不通过

**常见原因**：
- 权限申请过多
- 功能描述不清晰
- 使用场景说明不足

**解决**：
1. 仅申请必需权限
2. 详细填写功能描述
3. 提供使用场景截图

---

## 📚 参考资料

1. [飞书机器人概述](https://open.feishu.cn/document/client-docs/bot-v3/bot-overview)
2. [应用机器人开发指南](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/develop-robots/quick-start)
3. [自定义机器人配置指南](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/develop-robots/custom-bot)
4. [飞书消息开放能力](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/introduction)
5. [飞书卡片开发指南](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/feishu-card-overview)

---

**最后更新**：2026 年 4 月 12 日  
**小柔 AI 版本**：v5.25.8
