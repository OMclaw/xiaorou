#!/usr/bin/env python3
"""test_face_consistency.py - 脸部一致性优化测试脚本

测试不同优化方案的效果对比。

用法：
    python3 test_face_consistency.py --mode prompt|enhancer|compare
"""

import os
import sys
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


def test_prompt_optimization():
    """测试 Prompt 优化效果"""
    logger.info("📝 测试 Prompt 优化方案...")
    
    from image_analyzer import build_reference_prompt
    
    # 测试用例
    test_description = "咖啡厅，靠窗座位，自然光，白色衬衫，黑色长发，手持咖啡杯"
    prompt = build_reference_prompt(test_description)
    
    logger.info("✅ 生成的 Prompt:")
    print("\n" + "="*80)
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print("="*80 + "\n")
    
    # 验证关键指令是否存在
    required_keywords = [
        "极高优先级",
        "脸部锁定",
        "完全不变",
        "绝对不能变成其他人",
        "反向提示词"
    ]
    
    missing = [kw for kw in required_keywords if kw not in prompt]
    if missing:
        logger.warning(f"⚠️  Prompt 缺少关键指令：{missing}")
        return False
    
    logger.info("✅ Prompt 优化验证通过")
    return True


def test_face_enhancer():
    """测试换脸增强模块"""
    logger.info("🎭 测试换脸增强模块...")
    
    # 检查依赖
    try:
        import insightface
        import cv2
        logger.info("✅ 依赖检查通过")
    except ImportError as e:
        logger.error(f"❌ 依赖缺失：{e}")
        logger.info("请运行：pip install insightface onnxruntime-gpu opencv-python")
        return False
    
    # 检查文件
    script_dir = Path(__file__).parent
    character_path = script_dir.parent / 'assets/default-character.png'
    
    if not character_path.exists():
        logger.error(f"❌ 头像文件不存在：{character_path}")
        return False
    
    logger.info(f"✅ 头像文件存在：{character_path}")
    
    # 测试人脸检测
    try:
        from face_enhancer import init_face_analysis, extract_face_features
        import cv2
        
        app = init_face_analysis()
        face = extract_face_features(app, str(character_path))
        
        if face is None:
            logger.error("❌ 未能在头像中检测到人脸")
            return False
        
        logger.info(f"✅ 人脸检测成功，边界框：{face['bbox']}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_selfie_generation():
    """测试自拍生成流程"""
    logger.info("📸 测试自拍生成流程...")
    
    # 检查配置
    try:
        from config import config
        api_key = config.get_api_key()
        logger.info("✅ API Key 配置正确")
    except Exception as e:
        logger.error(f"❌ API Key 配置错误：{e}")
        return False
    
    # 检查头像文件
    from selfie import validate_character_image
    try:
        image_path = validate_character_image()
        logger.info(f"✅ 头像文件验证通过：{image_path}")
    except Exception as e:
        logger.error(f"❌ 头像文件验证失败：{e}")
        return False
    
    # 测试 prompt 构建
    from selfie import build_prompt
    mode, prompt = build_prompt("咖啡厅自拍")
    logger.info(f"✅ Prompt 构建成功，模式：{mode}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='小柔 AI - 脸部一致性优化测试')
    parser.add_argument('--mode', choices=['prompt', 'enhancer', 'compare', 'all'],
                       default='all', help='测试模式')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    results = {}
    
    if args.mode in ['prompt', 'all']:
        results['prompt'] = test_prompt_optimization()
    
    if args.mode in ['enhancer', 'all']:
        results['enhancer'] = test_face_enhancer()
    
    if args.mode in ['compare', 'all']:
        results['selfie'] = test_selfie_generation()
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("="*80)
    
    if all_passed:
        print("\n✅ 所有测试通过！优化方案已就绪。")
        print("\n下一步：")
        print("  1. 安装换脸依赖：pip install insightface onnxruntime-gpu opencv-python")
        print("  2. 测试自拍生成：bash scripts/aevia.sh '发张自拍' feishu")
        print("  3. 查看详细文档：cat FACE_CONSISTENCY_OPTIMIZATION.md")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败，请检查上方错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    main()
