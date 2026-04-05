#!/usr/bin/env python3
"""selfie.py 单元测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.selfie import sanitize_input, is_safe_path
from pathlib import Path
import pytest


class TestSanitizeInput:
    """测试输入净化函数"""
    
    def test_removes_dangerous_chars(self):
        """测试移除危险字符"""
        assert sanitize_input("test`$()") == "test"
        assert sanitize_input("hello;world") == "helloworld"
        assert sanitize_input("test|pipe") == "testpipe"
    
    def test_removes_control_chars(self):
        """测试移除控制字符"""
        assert sanitize_input("test\n\r") == "test"
    
    def test_truncates_long_input(self):
        """测试长输入截断"""
        long_input = "a" * 1000
        result = sanitize_input(long_input)
        assert len(result) <= 500
    
    def test_empty_input(self):
        """测试空输入"""
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


class TestIsSafePath:
    """测试路径安全检查函数"""
    
    def test_safe_path(self):
        """测试安全路径"""
        base = Path("/tmp/openclaw")
        assert is_safe_path(base, "/tmp/openclaw/test.jpg") == True
    
    def test_path_traversal(self):
        """测试路径遍历防护"""
        base = Path("/tmp/openclaw")
        assert is_safe_path(base, "/tmp/../etc/passwd") == False
        assert is_safe_path(base, "/tmp/openclaw/../../etc/passwd") == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
