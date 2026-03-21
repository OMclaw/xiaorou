# 更新日志

所有重要的项目更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 🔒 安全性修复
- 修复 API Key 硬编码风险，改为从环境变量或配置文件安全加载
- 添加用户输入验证，防止命令注入攻击
- 实现路径安全验证，防止目录遍历攻击
- 日志中脱敏 API Key，避免敏感信息泄露

### 📦 新增文件
- 添加 `.gitignore` 文件，排除敏感文件和生成文件
- 添加 `requirements.txt`，声明 Python 依赖
- 添加 `LICENSE` 文件（MIT 许可证）
- 添加 `CONTRIBUTING.md`，贡献指南
- 添加 `CHANGELOG.md`，更新日志

### 🐛 错误处理
- 统一 stdout/stderr 输出（错误信息输出到 stderr）
- 添加详细的错误信息和异常处理
- 改进安装脚本，备份用户配置并询问是否覆盖

### 📝 文档改进
- 添加完整的文档字符串
- 添加代码注释
- 统一变量命名风格（遵循 PEP 8 和 Shell 最佳实践）

### ✨ 代码重构
- 拆分 `selfie.py` 中的 `generate_selfie` 函数为多个职责单一的函数
- 提取通用的安全函数（输入验证、路径验证、API Key 加载）
- 改进代码结构和可读性

---

## [1.0.0] - 2026-03-21

### 新增
- 初始版本发布
- 情感聊天功能（基于 Qwen3.5-plus）
- 自拍生成功能（基于 Wan2.6-image）
- 角色头像生成功能（基于 Z-image）
- 支持多平台（飞书/Telegram/Discord/WhatsApp）
- 自动配置加载

---

## 版本说明

### 语义化版本

- **主版本号（Major）**：不兼容的 API 更改
- **次版本号（Minor）**：向后兼容的功能性新增
- **修订号（Patch）**：向后兼容的问题修复

### 更新类型

- `Added`：新增功能
- `Changed`：现有功能的变更
- `Deprecated`：即将移除的功能
- `Removed`：已移除的功能
- `Fixed`：Bug 修复
- `Security`：安全性修复
