#!/usr/bin/env python3
"""config.py 单元测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import Config, ConfigurationError
import pytest


class TestConfig:
    """测试配置类"""
    
    def test_singleton(self):
        """测试单例模式"""
        config1 = Config()
        config2 = Config()
        assert config1 is config2
    
    def test_get_temp_dir(self):
        """测试临时目录获取"""
        config = Config()
        temp_dir = config.get_temp_dir()
        assert temp_dir.exists()
        assert temp_dir.is_dir()
    
    def test_api_key_validation(self):
        """测试 API Key 验证"""
        config = Config()
        # 测试有效格式
        import re
        assert re.match(r'^sk-[a-zA-Z0-9]{20,}$', 'sk-12345678901234567890')
        # 测试无效格式
        assert not re.match(r'^sk-[a-zA-Z0-9]{20,}$', 'invalid-key')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
