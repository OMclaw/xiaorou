#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_tts.py - TTS 功能测试脚本

用于快速验证 TTS 功能是否正常工作
"""

import sys
import os
import tempfile

# 添加脚本目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from tts import text_to_speech, list_available_voices, get_api_key, validate_api_key


def test_get_api_key():
    """测试 API Key 获取功能"""
    print("测试 API Key 获取...")
    
    api_key = get_api_key()
    
    if api_key:
        masked = api_key[:5] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
        print(f"✓ 获取到 API Key: {masked}")
    else:
        print("⚠️  未找到 API Key")
        print("   请设置环境变量: export DASHSCOPE_API_KEY=sk-xxx")
        print("   或配置 ~/.openclaw/openclaw.json")
    
    return api_key


def test_validate_api_key():
    """测试 API Key 验证功能"""
    print("测试 API Key 验证...")
    
    # 有效 API Key
    assert validate_api_key("sk-abcdefghij1234567890abcd") == True, "有效 API Key 验证失败"
    assert validate_api_key("sk-ABCDEFGHIJKLMNOPQRSTUVWX") == True, "大写字母 API Key 验证失败"
    
    # 无效 API Key
    assert validate_api_key("") == False, "空 API Key 应该无效"
    assert validate_api_key("sk-short") == False, "过短 API Key 应该无效"
    assert validate_api_key("invalid-key") == False, "无效格式 API Key 应该无效"
    
    print("✓ API Key 验证测试通过")


def test_list_voices():
    """测试音色列表功能"""
    print("测试音色列表...")
    
    voices = list_available_voices()
    assert len(voices) > 0, "音色列表为空"
    assert "longqiang_v3" in voices, "默认音色不在列表中"
    
    print(f"✓ 音色列表测试通过 (共 {len(voices)} 种音色):")
    for voice in voices:
        marker = " (默认)" if voice == "longqiang_v3" else ""
        print(f"    - {voice}{marker}")


def test_tts_generation():
    """测试 TTS 生成功能（需要 API Key）"""
    print("测试 TTS 生成...")
    
    api_key = get_api_key()
    
    if not api_key or not validate_api_key(api_key):
        print("⚠️  未设置有效的 DASHSCOPE_API_KEY，跳过生成测试")
        print("   如需测试完整功能，请设置环境变量:")
        print("   export DASHSCOPE_API_KEY=sk-xxx")
        return
    
    # 生成临时文件
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        output_path = f.name
    
    try:
        # 测试生成
        success, message = text_to_speech(
            text="你好，我是小柔",
            output_path=output_path,
            voice="longqiang_v3",
            retries=1
        )
        
        if success:
            file_size = os.path.getsize(output_path)
            print(f"✓ TTS 生成测试通过 (文件大小：{file_size} bytes)")
        else:
            print(f"⚠️  TTS 生成失败：{message}")
    
    finally:
        # 清理临时文件
        if os.path.exists(output_path):
            os.unlink(output_path)


def main():
    """运行所有测试"""
    print("=" * 50)
    print("TTS 功能测试 (CosyVoice)")
    print("=" * 50)
    print()
    
    try:
        test_get_api_key()
        test_validate_api_key()
        test_list_voices()
        test_tts_generation()
        
        print()
        print("=" * 50)
        print("✓ 所有测试完成")
        print("=" * 50)
        return 0
    
    except AssertionError as e:
        print()
        print("=" * 50)
        print(f"✗ 测试失败：{e}")
        print("=" * 50)
        return 1
    except Exception as e:
        print()
        print("=" * 50)
        print(f"✗ 未知错误：{e}")
        print("=" * 50)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
