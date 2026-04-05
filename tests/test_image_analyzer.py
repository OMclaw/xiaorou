#!/usr/bin/env python3
"""image_analyzer.py 单元测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.image_analyzer import sanitize_input, build_reference_prompt
import pytest


class TestSanitizeInput:
    """测试输入净化函数"""
    
    def test_removes_dangerous_chars(self):
        """测试移除危险字符"""
        assert "`$()" not in sanitize_input("test`$()")
    
    def test_empty_input(self):
        """测试空输入"""
        assert sanitize_input("") == ""


class TestBuildReferencePrompt:
    """测试 Prompt 构建函数"""
    
    def test_contains_face_lock_instructions(self):
        """测试包含脸部锁定指令"""
        prompt = build_reference_prompt("咖啡厅，白色衬衫")
        assert "极高优先级" in prompt
        assert "脸部锁定" in prompt
        assert "完全不变" in prompt
    
    def test_contains_negative_tags(self):
        """测试包含反向提示词"""
        prompt = build_reference_prompt("咖啡厅")
        assert "反向提示词" in prompt
        assert "bad anatomy" in prompt


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
