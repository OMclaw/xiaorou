#!/usr/bin/env python3
"""test_feishu_target_compat.py - 测试飞书用户 ID 格式兼容性

测试所有支持的格式：
- ou_xxx（open_id）
- user:ou_xxx（带前缀的 open_id）
- on_xxx（union_id）
- user:on_xxx（带前缀的 union_id）
- user_xxx（user_id）
- user:user_xxx（带前缀的 user_id）

用法：
    python3 test_feishu_target_compat.py
"""

import sys
sys.path.insert(0, '.')

from config import normalize_feishu_target

# 测试用例
TEST_CASES = [
    # (输入，期望输出，描述)
    ("ou_0668d1ec503978ef15adadd736f34c46", ("ou_0668d1ec503978ef15adadd736f34c46", "open_id"), "标准 open_id"),
    ("user:ou_0668d1ec503978ef15adadd736f34c46", ("ou_0668d1ec503978ef15adadd736f34c46", "open_id"), "带 user: 前缀的 open_id"),
    ("on_1234567890abcdef", ("on_1234567890abcdef", "union_id"), "标准 union_id"),
    ("user:on_1234567890abcdef", ("on_1234567890abcdef", "union_id"), "带 user: 前缀的 union_id"),
    ("user_abc123", ("user_abc123", "user_id"), "标准 user_id"),
    ("user:user_abc123", ("user_abc123", "user_id"), "带 user: 前缀的 user_id"),
]

INVALID_CASES = [
    ("", "空字符串"),
    ("invalid_id", "无效格式"),
    ("ou_", "不完整的 open_id"),
    ("123456", "纯数字"),
]

def test_valid_cases():
    """测试有效格式"""
    print("=" * 70)
    print("测试有效格式")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for input_val, expected, description in TEST_CASES:
        try:
            result = normalize_feishu_target(input_val)
            if result == expected:
                print(f"✅ PASS: {description}")
                print(f"   输入：{input_val}")
                print(f"   输出：{result}")
                passed += 1
            else:
                print(f"❌ FAIL: {description}")
                print(f"   输入：{input_val}")
                print(f"   期望：{expected}")
                print(f"   实际：{result}")
                failed += 1
        except Exception as e:
            print(f"❌ ERROR: {description}")
            print(f"   输入：{input_val}")
            print(f"   异常：{e}")
            failed += 1
        print()
    
    return passed, failed


def test_invalid_cases():
    """测试无效格式（应该抛出 ValueError）"""
    print("=" * 70)
    print("测试无效格式（应该报错）")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for input_val, description in INVALID_CASES:
        try:
            result = normalize_feishu_target(input_val)
            print(f"❌ FAIL: {description}")
            print(f"   输入：{input_val}")
            print(f"   期望：抛出 ValueError")
            print(f"   实际：{result}（未抛出异常）")
            failed += 1
        except ValueError as e:
            print(f"✅ PASS: {description}")
            print(f"   输入：{input_val}")
            print(f"   异常：{e}")
            passed += 1
        except Exception as e:
            print(f"⚠️  UNEXPECTED: {description}")
            print(f"   输入：{input_val}")
            print(f"   异常类型：{type(e).__name__}")
            print(f"   异常：{e}")
            failed += 1
        print()
    
    return passed, failed


def main():
    print("\n🧪 飞书用户 ID 格式兼容性测试\n")
    
    valid_passed, valid_failed = test_valid_cases()
    invalid_passed, invalid_failed = test_invalid_cases()
    
    total_passed = valid_passed + invalid_passed
    total_failed = valid_failed + invalid_failed
    total = total_passed + total_failed
    
    print("=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"总测试数：{total}")
    print(f"通过：{total_passed} ✅")
    print(f"失败：{total_failed} ❌")
    print(f"通过率：{total_passed/total*100:.1f}%" if total > 0 else "N/A")
    
    if total_failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
