# 贡献指南

欢迎为小柔 AI 项目做出贡献！

## 如何贡献

### 1. 报告问题

发现 Bug 或有功能建议？请创建 [Issue](https://github.com/OMclaw/xiaorou/issues)。

### 2. 提交代码

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

### 3. 开发环境

```bash
# 克隆仓库
git clone https://github.com/OMclaw/xiaorou.git
cd xiaorou

# 安装依赖
pip install -r requirements.txt

# 运行测试
bash scripts/test.sh
```

## 代码规范

### Shell 脚本

- 使用 `shellcheck` 进行静态分析
- 遵循 [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- 使用 `set -euo pipefail` 确保错误处理

### Python 代码

- 遵循 [PEP 8](https://pep8.org/) 风格指南
- 使用 `black` 进行代码格式化
- 添加文档字符串和类型注解
- 编写单元测试

### 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具相关

示例：
```
fix: 修复自拍生成的 API 调用超时问题
feat: 添加新的自拍模式支持
docs: 更新安装指南
```

## 安全指南

- **不要**提交 API Key 或其他敏感信息
- **不要**硬编码凭证
- 使用环境变量或配置文件管理敏感数据
- 对所有用户输入进行验证

## 测试

提交 PR 前请确保：

- [ ] 代码通过所有现有测试
- [ ] 添加了新功能的测试
- [ ] 代码通过 `shellcheck`（Shell 脚本）
- [ ] 代码通过 `flake8`（Python 代码）

## 许可证

通过贡献代码，您同意根据本项目的 [MIT 许可证](LICENSE) 授权您的贡献。

---

感谢您的贡献！🦞❤️
