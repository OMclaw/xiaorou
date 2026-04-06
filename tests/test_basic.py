#!/usr/bin/env python3
"""test_basic.py - 小柔 AI 基础单元测试框架

运行测试：
    python3 -m pytest tests/test_basic.py -v

测试覆盖：
- 配置模块
- 路径安全检查
- 输入净化
- 模型参数格式
"""

import pytest
import sys
import os
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestConfig:
    """配置模块测试"""
    
    def test_config_singleton(self):
        """测试 Config 单例模式"""
        from config import Config
        config1 = Config()
        config2 = Config()
        assert config1 is config2, "Config 应该是单例"
    
    def test_temp_dir_creation(self):
        """测试临时目录创建"""
        from config import config
        temp_dir = config.get_temp_dir()
        assert temp_dir.exists(), "临时目录应该存在"
        assert temp_dir.stat().st_mode & 0o700 == 0o700, "临时目录权限应该是 700"


class TestPathSafety:
    """路径安全检查测试"""
    
    def test_safe_path_allowed(self):
        """测试允许的路径"""
        from selfie import is_safe_path
        from config import config
        
        # 测试允许的目录
        test_paths = [
            '/tmp/openclaw/test.jpg',
            '/tmp/xiaorou/test.png',
        ]
        
        for test_path in test_paths:
            # 创建临时文件用于测试
            Path(test_path).parent.mkdir(parents=True, exist_ok=True)
            Path(test_path).touch(exist_ok=True)
            assert is_safe_path(config.get_temp_dir(), test_path), f"{test_path} 应该是安全的"
    
    def test_safe_path_forbidden(self):
        """测试禁止的路径"""
        from selfie import is_safe_path
        from config import config
        
        # 测试危险的目录
        forbidden_paths = [
            '/etc/passwd',
            '/home/admin/.ssh/id_rsa',
            '/tmp/openclaw_evil/test.jpg',  # 前缀攻击
        ]
        
        for test_path in forbidden_paths:
            assert not is_safe_path(config.get_temp_dir(), test_path), f"{test_path} 应该被禁止"


class TestInputSanitization:
    """输入净化测试"""
    
    def test_sanitize_input_removes_dangerous_chars(self):
        """测试移除危险字符"""
        from selfie import sanitize_input
        
        dangerous_inputs = [
            'test; rm -rf /',
            'test$(whoami)',
            'test`id`',
            'test|cat /etc/passwd',
        ]
        
        for dangerous in dangerous_inputs:
            sanitized = sanitize_input(dangerous)
            assert ';' not in sanitized, "应该移除分号"
            assert '$' not in sanitized, "应该移除美元符号"
            assert '`' not in sanitized, "应该移除反引号"
            assert '|' not in sanitized, "应该移除管道符"
    
    def test_sanitize_input_preserves_chinese(self):
        """测试保留中文字符"""
        from selfie import sanitize_input
        
        chinese_text = "小柔在海边看日落"
        sanitized = sanitize_input(chinese_text)
        assert sanitized == chinese_text, "中文字符应该被保留"


class TestModelParams:
    """模型参数测试"""
    
    def test_size_format_for_models(self):
        """测试不同模型的 size 参数格式"""
        # wan2.7 系列使用 1K
        assert get_size_for_model('wan2.7-image') == '1K'
        assert get_size_for_model('wan2.7-image-pro') == '1K'
        
        # qwen-image 系列使用 1024*1024
        assert get_size_for_model('qwen-image-2.0') == '1024*1024'
        assert get_size_for_model('qwen-image-2.0-pro') == '1024*1024'


def get_size_for_model(model_name: str) -> str:
    """根据模型名称返回正确的 size 参数格式"""
    if 'qwen-image' in model_name:
        return '1024*1024'
    else:
        return '1K'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
