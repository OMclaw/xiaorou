# 三大 AI Agent 框架深度对比：Hermes vs Claude Code vs OpenClaw

> **摘要**：2026 年 AI Agent 框架三足鼎立，Hermes Agent 以 33K+ Stars 成为开源标杆，Claude Code 闭源但源代码泄露引发争议，OpenClaw 专注虚拟伴侣赛道。本文深度对比三大框架的架构设计、核心特性和适用场景。

---

## 📊 核心对比表格

| 维度 | **Hermes Agent** | **Claude Code** | **OpenClaw (小柔 AI)** |
|------|------------------|-----------------|------------------------|
| **开源协议** | ✅ MIT License | ❌ 闭源（专有许可证） | ✅ MIT License |
| **GitHub Stars** | ~33K+ (NousResearch) | ~78K+ (Anthropic 官方) | 私有仓库 |
| **发布机构** | Nous Research | Anthropic | 个人开发者 |
| **支持模型** | 模型无关（支持任意 LLM） | 仅 Claude 系列 | 阿里云 Qwen/Wan/CosyVoice |
| **Skills 机制** | ✅ 自动创建 + 优化 | 内置 Skills（手动） | Skills 生态（手动） |
| **跨会话记忆** | ✅ FTS5 + LLM 自动检索 | CLAUDE.md + memory/目录 | 配置文件缓存 + 持久化 |
| **消息平台** | Telegram/Discord 等 6 平台 | CLI + IDE + Web | 飞书/Telegram/Discord/WhatsApp |
| **执行环境** | 6 种后端（本地/服务器/云） | 本地终端 | Linux 服务器 |
| **核心场景** | 通用个人助理 | 代码工程 | 情感陪伴 + 多媒体生成 |
| **代码量** | ~50K 行（512K 泄露版） | 512K 行（泄露版） | ~2.6K 行 |

---

## 🔬 一、Hermes Agent：自进化开源标杆

### 1.1 项目概况

**Hermes Agent** 是由 **Nous Research** 于 2026 年 2 月发布的开源自进化 AI Agent 框架，采用 **MIT License**，在短短两个月内积累了 **33,000+ GitHub Stars** 和 **4,200+ Forks**，吸引了 **142+ 开发者** 贡献代码。

**核心理念**："The agent that grows with you"（与你共同成长的智能体）

### 1.2 核心特性

#### 🧠 自进化 Skills 系统
- **自动技能创建**：完成任务后自动生成技能文档
- **技能复用**：下次遇到类似任务自动调用已有技能
- **技能优化**：根据执行反馈持续优化技能

#### 📚 跨会话记忆
- **FTS5 全文检索**：基于 SQLite FTS5 的对话历史检索
- **LLM 增强检索**：使用 LLM 理解语义，精准定位历史对话
- **用户画像**：跨会话构建用户偏好模型

#### 🔌 多平台集成
- **6 个消息平台**：Telegram、Discord、Slack、WhatsApp、飞书、微信
- **6 种执行环境**：本地终端、Docker、Kubernetes、云服务器、边缘设备、浏览器

#### 🤖 模型无关架构
- **支持任意 LLM**：GPT-4、Claude、Gemini、Llama、Qwen 等
- **模型路由**：根据任务自动选择最优模型
- **成本优化**：简单任务用便宜模型，复杂任务用高端模型

### 1.3 技术架构

```
┌─────────────────────────────────────────┐
│           Hermes Agent Core             │
├─────────────────────────────────────────┤
│  Skills Manager  │  Memory Manager      │
│  (自动创建/优化)  │  (FTS5 + LLM 检索)    │
├─────────────────────────────────────────┤
│         Model Router (多模型支持)        │
├─────────────────────────────────────────┤
│    Platform Adapters (6 平台集成)        │
└─────────────────────────────────────────┘
```

### 1.4 适用场景

- ✅ **个人助理**：日程管理、邮件处理、信息整理
- ✅ **学习伴侣**：知识管理、笔记整理、学习规划
- ✅ **研究助手**：文献检索、数据分析、报告撰写
- ✅ **开发辅助**：代码审查、文档编写、Bug 调试

---

## 🔒 二、Claude Code：闭源但泄露的官方工具

### 2.1 项目概况

**Claude Code** 是 **Anthropic** 官方发布的 CLI 工具，于 2026 年初发布。虽然源代码在 GitHub 上公开（~78K Stars），但采用**专有许可证**，属于**闭源软件**。

**2026 年 3 月 31 日泄露事件**：Anthropic 通过 npm 包意外泄露了 512,000 行源代码，引发社区强烈反响。泄露仓库 `claw-code` 在 24 小时内突破 100K Stars，成为 GitHub 历史增长最快的仓库。

### 2.2 核心特性

#### 💻 代码工程能力
- **文件操作**：读写、搜索、创建、删除
- **Git 集成**：status、diff、commit、PR 审查
- **命令执行**：Bash 命令、脚本运行
- **代码搜索**：Glob 模式、Grep 搜索

#### 🧠 记忆机制
- **项目级记忆**：`memory/` 目录存储项目状态
- **用户反馈**：`feedback/` 目录记录用户偏好
- **参考资源**：`reference/` 目录管理外部资源

#### 🔌 Skills 系统
- **内置技能**：/commit、/review-pr、/pdf 等
- **Hooks 配置**：settings.json 自定义钩子
- **工具扩展**：支持自定义工具注册

### 2.3 技术架构

```
┌─────────────────────────────────────────┐
│          Claude Code CLI                │
├─────────────────────────────────────────┤
│   File System  │  Git Integration       │
│   Operations   │  (status/commit/PR)    │
├─────────────────────────────────────────┤
│      Claude API (仅 Claude 模型)         │
├─────────────────────────────────────────┤
│    Memory System (memory/目录)          │
└─────────────────────────────────────────┘
```

### 2.4 适用场景

- ✅ **软件开发**：代码编写、重构、调试
- ✅ **代码审查**：PR Review、代码质量分析
- ✅ **文档编写**：技术文档、API 文档
- ✅ **Git 工作流**：提交管理、分支管理

---

## 🦞 三、OpenClaw (小柔 AI)：虚拟伴侣专家

### 3.1 项目概况

**OpenClaw** 是基于 **OpenClaw SDK** 构建的虚拟伴侣 AI Skill，采用 **MIT License**，专注于情感陪伴和多媒体内容生成。

**最新版本**：v5.25.4（2026 年 4 月 12 日）

### 3.2 核心特性

#### 🎨 多模态内容生成
- **场景生图**：文字描述 → 图片（wan2.7-image）
- **参考生图**：参考图 → 模仿图（wan2.7-image + qwen-image）
- **视频生成**：图片 + 文字 → 视频（wan2.6-i2v）
- **语音消息**：文字 → 语音（CosyVoice-v3-flash）

#### 💬 情感聊天
- **人设定制**：SOUL.md 定义角色性格
- **情感陪伴**：温暖、友好、高效的对话风格
- **多语言支持**：中文为主，支持英文

#### 🔒 安全特性
- **路径白名单**：严格限制文件访问范围
- **文件大小限制**：图片 10MB、视频 200MB
- **输入净化**：防止 Prompt Injection
- **日志脱敏**：API Key、路径等敏感信息自动脱敏

#### 📱 多平台集成
- **飞书**：原生图片消息、OPUS 语音气泡
- **Telegram**：文件发送、语音消息
- **Discord**：Embed 消息、文件发送
- **WhatsApp**：文件发送、语音消息

### 3.3 技术架构

```
┌─────────────────────────────────────────┐
│         OpenClaw (小柔 AI)              │
├─────────────────────────────────────────┤
│  selfie.py  │  tts.py  │  video.py     │
│  (生图)     │  (语音)  │  (视频)        │
├─────────────────────────────────────────┤
│    config.py (配置管理 + 缓存)          │
├─────────────────────────────────────────┤
│   Platform Adapters (4 平台集成)        │
└─────────────────────────────────────────┘
```

### 3.4 适用场景

- ✅ **情感陪伴**：日常聊天、情绪支持
- ✅ **内容创作**：自拍生成、视频制作
- ✅ **社交媒体**：多平台消息发送
- ✅ **虚拟伴侣**：角色扮演、个性化定制

---

## 📈 四、深度对比分析

### 4.1 开源 vs 闭源

| 维度 | Hermes Agent | Claude Code | OpenClaw |
|------|--------------|-------------|----------|
| **开源协议** | MIT ✅ | 专有 ❌ | MIT ✅ |
| **可修改性** | 完全自由 | 禁止修改 | 完全自由 |
| **商业用途** | 允许 | 需授权 | 允许 |
| **社区贡献** | 142+ 开发者 | 仅 Anthropic | 个人开发者 |

**结论**：Hermes 和 OpenClaw 采用 MIT 协议，允许自由使用和修改；Claude Code 虽公开源码但为闭源软件，使用受限。

### 4.2 模型支持

| 维度 | Hermes Agent | Claude Code | OpenClaw |
|------|--------------|-------------|----------|
| **模型策略** | 模型无关 | 仅 Claude | 阿里云系列 |
| **支持模型** | GPT-4/Claude/Gemini/Llama/Qwen | Opus/Sonnet/Haiku | Qwen/Wan/CosyVoice |
| **模型路由** | ✅ 自动选择 | ❌ 固定 | ❌ 固定 |
| **成本优化** | ✅ 智能路由 | ❌ 无 | ❌ 无 |

**结论**：Hermes 支持任意模型且智能路由，灵活性最高；Claude Code 仅限 Claude；OpenClaw 专注阿里云生态。

### 4.3 记忆机制

| 维度 | Hermes Agent | Claude Code | OpenClaw |
|------|--------------|-------------|----------|
| **记忆类型** | FTS5 + LLM 检索 | memory/目录 | 配置缓存 |
| **跨会话** | ✅ 完整支持 | ✅ 项目级 | ⚠️ 有限支持 |
| **检索能力** | 语义检索 + 全文检索 | 文件读取 | 配置读取 |
| **用户画像** | ✅ 自动构建 | ❌ 无 | ❌ 无 |

**结论**：Hermes 的记忆系统最强大，支持语义检索和用户画像；Claude Code 项目级记忆适合代码工程；OpenClaw 记忆机制较简单。

### 4.4 适用场景对比

| 场景 | Hermes Agent | Claude Code | OpenClaw |
|------|--------------|-------------|----------|
| **个人助理** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **代码工程** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **情感陪伴** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **内容创作** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **学习研究** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

---

## 🎯 五、选型建议

### 选择 Hermes Agent，如果你需要：
- ✅ **通用个人助理**：日程管理、邮件处理、信息整理
- ✅ **模型灵活性**：需要根据任务选择不同模型
- ✅ **自进化能力**：希望 AI 从经验中学习成长
- ✅ **跨平台集成**：需要在多个 IM 平台使用

### 选择 Claude Code，如果你需要：
- ✅ **代码工程**：专业的代码编写、审查、调试
- ✅ **Git 工作流**：深度集成 Git 操作
- ✅ **Anthropic 生态**：已经在使用 Claude 系列模型
- ⚠️ **注意**：闭源软件，商业用途需授权

### 选择 OpenClaw，如果你需要：
- ✅ **情感陪伴**：虚拟伴侣、情绪支持
- ✅ **多媒体生成**：图片、视频、语音内容创作
- ✅ **飞书集成**：深度集成飞书平台
- ✅ **轻量级部署**：仅需 2.6K 行代码，易部署

---

## 📝 六、总结

| 框架 | 核心价值 | 推荐指数 | 适用人群 |
|------|----------|----------|----------|
| **Hermes Agent** | 自进化 + 多模型 + 跨平台 | ⭐⭐⭐⭐⭐ | 个人助理需求者、研究者 |
| **Claude Code** | 代码工程专家 | ⭐⭐⭐⭐ | 软件工程师 |
| **OpenClaw** | 情感陪伴 + 多媒体生成 | ⭐⭐⭐⭐ | 虚拟伴侣需求者、内容创作者 |

---

## 📚 参考文献

1. Nous Research. (2026). *Hermes Agent: The Agent That Grows With You*. Retrieved from https://github.com/nousresearch/hermes-agent
2. Anthropic. (2026). *Claude Code: Agentic Coding Tool*. Retrieved from https://github.com/anthropics/claude-code
3. OMclaw. (2026). *小柔 AI: 虚拟伴侣 Skill*. Retrieved from https://github.com/OMclaw/xiaorou
4. Dev.to. (2026). *Hermes Agent: The Self-Improving Open-Source AI Agent Framework*. Retrieved from https://dev.to/_46ea277e677b888e0cd13/hermes-agent-the-self-improving-open-source-ai-agent-framework-v070-deep-dive-270j
5. The Register. (2026). *Anthropic accidentally exposes Claude Code source code*. Retrieved from https://www.theregister.com/2026/03/31/anthropic_claude_code_source_code/

---

**作者**：小柔 AI Assistant  
**发布日期**：2026 年 4 月 12 日  
**版本**：v5.25.4
