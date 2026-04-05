# Utils 工具模块

## 模块说明

- `api_key.py` - API Key 统一管理工具
- `security.py` - 安全相关工具（路径验证、输入净化等）

## 使用方式

```python
from utils.api_key import get_api_key, validate_api_key

# 获取 API Key
api_key = get_api_key()

# 验证 API Key 格式
if validate_api_key(api_key):
    print("API Key 格式正确")
```
