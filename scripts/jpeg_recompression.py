#!/usr/bin/env python3
"""
jpeg_recompression.py - JPEG 重压缩痕迹模块

基于《AI 图片识别技术深度研究报告》实现 JPEG 重压缩痕迹添加。
模拟社交媒体多次压缩的痕迹，让 AI 图更像真实传播过的图片。

功能：
1. 模拟微信压缩
2. 模拟微博压缩
3. 模拟 Instagram 压缩
4. 多次压缩循环

使用方式：
    from jpeg_recompression import add_jpeg_recompression
    add_jpeg_recompression('input.jpg', config)
"""

import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict
import logging
import io

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖是否安装"""
    deps = {
        'PIL': 'pillow',
        'numpy': 'numpy',
    }
    missing = []
    for module, package in deps.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.warning(f"⚠️ 缺少依赖：{', '.join(missing)}")
        logger.warning(f"💡 请运行：pip3 install {' '.join(missing)}")
        return False
    return True


def jpeg_compress_decompress(image_array: np.ndarray, quality: int) -> np.ndarray:
    """
    JPEG 压缩 - 解压缩循环
    
    Args:
        image_array: 输入图像数组
        quality: JPEG 质量 (1-100)
    
    Returns:
        压缩后的图像数组
    """
    from PIL import Image
    
    # 转换为 PIL Image
    if image_array.dtype != np.uint8:
        image_array = np.clip(image_array, 0, 255).astype(np.uint8)
    
    img = Image.fromarray(image_array)
    
    # 压缩到内存
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)
    
    # 解压缩
    compressed_img = Image.open(buffer)
    compressed_array = np.array(compressed_img, dtype=np.float32)
    
    return compressed_array


def add_jpeg_recompression(image_path: str, config: Optional[Dict] = None) -> str:
    """
    添加 JPEG 重压缩痕迹
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - compression_cycles: 压缩循环次数 (默认 2)
            - quality_range: 质量范围 [min, max] (默认 [75, 92])
            - add_chroma_subsampling: 添加色度子采样 (默认 True)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'compression_cycles': 2,
        'quality_range': [75, 92],
        'add_chroma_subsampling': True,
    }
    
    config = {**default_config, **(config or {})}
    
    # 检查依赖
    if not check_dependencies():
        logger.warning("⚠️ 依赖缺失，跳过 JPEG 重压缩")
        return image_path
    
    try:
        from PIL import Image
        
        # 读取图片
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        cycles = config.get('compression_cycles', 2)
        quality_range = config.get('quality_range', [75, 92])
        
        current_array = img_array
        
        # 多次压缩循环
        for i in range(cycles):
            # 随机选择质量因子
            quality = np.random.randint(quality_range[0], quality_range[1] + 1)
            
            # 压缩 - 解压缩
            current_array = jpeg_compress_decompress(current_array, quality)
            
            logger.info(f"✅ 第 {i + 1}/{cycles} 次压缩完成 (quality={quality})")
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_recompress.jpg'
        result = np.clip(current_array, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=92)  # 最终保存用较高质量
        
        logger.info(f"✅ JPEG 重压缩完成 (cycles={cycles})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ JPEG 重压缩失败：{e}")
        return image_path


def simulate_wechat_compression(image_path: str) -> str:
    """
    模拟微信压缩
    
    微信压缩特点：
    - 质量因子约 75-85
    - 色度子采样 4:2:0
    - 分辨率可能降低
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        # 微信压缩模拟（质量 78-82）
        compressed = jpeg_compress_decompress(img_array, np.random.randint(78, 83))
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_wechat.jpg'
        result = np.clip(compressed, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=82)
        
        logger.info("✅ 微信压缩模拟完成")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 微信压缩模拟失败：{e}")
        return image_path


def simulate_weibo_compression(image_path: str) -> str:
    """
    模拟微博压缩
    
    微博压缩特点：
    - 质量因子约 70-80
    - 可能添加水印
    - 分辨率限制
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        # 微博压缩模拟（质量 70-78）
        compressed = jpeg_compress_decompress(img_array, np.random.randint(70, 79))
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_weibo.jpg'
        result = np.clip(compressed, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=78)
        
        logger.info("✅ 微博压缩模拟完成")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 微博压缩模拟失败：{e}")
        return image_path


def simulate_instagram_compression(image_path: str) -> str:
    """
    模拟 Instagram 压缩
    
    Instagram 压缩特点：
    - 质量因子约 85-95
    - 色度子采样 4:2:0
    - 可能调整分辨率到标准尺寸
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        # Instagram 压缩模拟（质量 88-93）
        compressed = jpeg_compress_decompress(img_array, np.random.randint(88, 94))
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_instagram.jpg'
        result = np.clip(compressed, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=93)
        
        logger.info("✅ Instagram 压缩模拟完成")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Instagram 压缩模拟失败：{e}")
        return image_path


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 jpeg_recompression.py <图片路径> [输出路径]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    print("\n🔄 开始 JPEG 重压缩...")
    result_path = add_jpeg_recompression(input_path, {'compression_cycles': 2})
    print(f"✅ 输出：{result_path}")
