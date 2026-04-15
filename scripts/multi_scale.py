#!/usr/bin/env python3
"""
multi_scale.py - 多尺度特征一致性模块

基于《AI 图片识别技术深度研究报告》实现多尺度反检测技术。
AI 生成图像在不同尺度下特征不一致，本模块通过多尺度处理来优化。

功能：
1. 图像金字塔提取 - 多尺度表示
2. 多尺度一致性处理 - 在各尺度上优化特征
3. 金字塔融合 - 无缝融合多尺度结果

技术原理：
- AI 图在单一尺度上可能看起来真实
- 但在多尺度分析下会暴露不一致性
- 通过在多个尺度上优化，让图像在所有尺度上都表现自然

使用方式：
    from multi_scale import apply_multi_scale_consistency
    apply_multi_scale_consistency('input.jpg')
"""

import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖是否安装"""
    deps = {
        'PIL': 'pillow',
        'numpy': 'numpy',
        'scipy': 'scipy',
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


def extract_pyramid(image: np.ndarray, scales: List[float] = None) -> List[np.ndarray]:
    """
    提取高斯金字塔
    
    Args:
        image: 输入图像数组 (H, W, C)
        scales: 尺度列表，默认 [1.0, 0.5, 0.25]
    
    Returns:
        金字塔图像列表
    """
    if scales is None:
        scales = [1.0, 0.5, 0.25]
    
    from scipy.ndimage import gaussian_filter, zoom
    
    pyramid = []
    
    for scale in scales:
        if scale == 1.0:
            pyramid.append(image.copy())
        else:
            # 高斯模糊 + 下采样
            blurred = gaussian_filter(image, sigma=1.0 / scale)
            new_shape = tuple(int(dim * scale) for dim in image.shape)
            resized = zoom(blurred, [scale, scale, 1] if image.ndim == 3 else [scale, scale])
            pyramid.append(resized)
    
    return pyramid


def laplacian_pyramid(image: np.ndarray, levels: int = 4) -> List[np.ndarray]:
    """
    提取拉普拉斯金字塔
    
    技术原理：
    - 拉普拉斯金字塔 = 高斯金字塔相邻层差分
    - 捕捉不同尺度的细节信息
    
    Args:
        image: 输入图像数组
        levels: 金字塔层数
    
    Returns:
        拉普拉斯金字塔列表
    """
    from scipy.ndimage import gaussian_filter, zoom
    
    # 先构建高斯金字塔
    gaussian_pyramid = [image.astype(np.float32)]
    
    for i in range(levels - 1):
        prev = gaussian_pyramid[-1]
        # 高斯模糊
        blurred = gaussian_filter(prev, sigma=1.0)
        # 下采样
        new_shape = tuple(dim // 2 for dim in prev.shape[:2])
        if image.ndim == 3:
            resized = zoom(blurred, [0.5, 0.5, 1.0])[:new_shape[0], :new_shape[1], :]
        else:
            resized = zoom(blurred, 0.5)[:new_shape[0], :new_shape[1]]
        gaussian_pyramid.append(resized)
    
    # 构建拉普拉斯金字塔
    laplacian_pyramid = []
    for i in range(levels - 1):
        # 上采样下一层
        expanded = zoom(gaussian_pyramid[i + 1], 2.0)
        if image.ndim == 3:
            expanded = expanded[:gaussian_pyramid[i].shape[0], :gaussian_pyramid[i].shape[1], :]
        else:
            expanded = expanded[:gaussian_pyramid[i].shape[0], :gaussian_pyramid[i].shape[1]]
        
        # 差分
        laplacian = gaussian_pyramid[i] - expanded
        laplacian_pyramid.append(laplacian)
    
    # 最后一层是高斯金字塔的顶层
    laplacian_pyramid.append(gaussian_pyramid[-1])
    
    return laplacian_pyramid


def apply_multi_scale_consistency(image_path: str, config: Optional[Dict] = None) -> str:
    """
    应用多尺度一致性处理
    
    技术原理：
    - 在每个尺度上应用一致性优化
    - 增强边缘和纹理的一致性
    - 减少 AI 生成的尺度不一致伪影
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - pyramid_levels: 金字塔层数 (默认 4)
            - consistency_strength: 一致性强度 (默认 0.3)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'pyramid_levels': 4,
        'consistency_strength': 0.3,
    }
    
    config = {**default_config, **(config or {})}
    
    try:
        from PIL import Image
        from scipy.ndimage import gaussian_filter, bilateral_filter
        
        # 读取图片
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        # 提取拉普拉斯金字塔
        levels = config.get('pyramid_levels', 4)
        laplacian = laplacian_pyramid(img_array, levels=levels)
        
        # 在每层上应用一致性优化
        optimized_laplacian = []
        for i, layer in enumerate(laplacian):
            # 对细节层应用边缘保持平滑
            if i < levels - 1:  # 不是最底层
                # 双边滤波保持边缘
                try:
                    # scipy 的 bilateral_filter 可能需要较新版本
                    optimized = bilateral_filter(layer, sigma_color=0.1, sigma_spatial=2.0)
                except:
                    # fallback: 简单高斯滤波
                    optimized = gaussian_filter(layer, sigma=0.5)
            else:
                optimized = layer
            optimized_laplacian.append(optimized)
        
        # 融合拉普拉斯金字塔
        result = optimized_laplacian[-1]
        for i in range(levels - 2, -1, -1):
            # 上采样
            from scipy.ndimage import zoom
            expanded = zoom(result, 2.0)
            if img_array.ndim == 3:
                target_shape = optimized_laplacian[i].shape
                expanded = expanded[:target_shape[0], :target_shape[1], :]
            else:
                target_shape = optimized_laplacian[i].shape
                expanded = expanded[:target_shape[0], :target_shape[1]]
            
            # 加上当前层
            result = expanded + optimized_laplacian[i]
        
        # 裁剪到有效范围
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_multi_scale.jpg'
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 多尺度一致性处理完成 (levels={levels})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 多尺度一致性处理失败：{e}")
        return image_path


def fuse_pyramid(pyramid_images: List[np.ndarray], weights: List[float] = None) -> np.ndarray:
    """
    融合金字塔图像
    
    Args:
        pyramid_images: 金字塔图像列表
        weights: 每层权重，默认 None（自动计算）
    
    Returns:
        融合后的图像
    """
    if weights is None:
        # 默认权重：底层权重大，顶层权重小
        weights = [1.0 / len(pyramid_images)] * len(pyramid_images)
    
    # 将所有图像 resize 到相同尺寸
    target_shape = pyramid_images[0].shape[:2]
    
    fused = np.zeros_like(pyramid_images[0], dtype=np.float32)
    
    for img, weight in zip(pyramid_images, weights):
        from scipy.ndimage import zoom
        
        scale_y = target_shape[0] / img.shape[0]
        scale_x = target_shape[1] / img.shape[1]
        
        if img.ndim == 3:
            resized = zoom(img, [scale_y, scale_x, 1.0])
        else:
            resized = zoom(img, [scale_y, scale_x])
        
        # 裁剪到目标尺寸
        resized = resized[:target_shape[0], :target_shape[1], ...] if img.ndim == 3 else resized[:target_shape[0], :target_shape[1]]
        
        fused += resized * weight
    
    return fused


def multi_scale_enhance(image_path: str, config: Optional[Dict] = None) -> str:
    """
    多尺度增强主函数
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - enable_pyramid: 是否使用金字塔处理 (默认 True)
            - pyramid_levels: 金字塔层数 (默认 4)
            - consistency_strength: 一致性强度 (默认 0.3)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'enable_pyramid': True,
        'pyramid_levels': 4,
        'consistency_strength': 0.3,
    }
    
    config = {**default_config, **(config or {})}
    config['pyramid_levels'] = int(os.environ.get('XIAOROU_PYRAMID_LEVELS', config['pyramid_levels']))
    
    # 检查依赖
    if not check_dependencies():
        logger.warning("⚠️ 依赖缺失，跳过多尺度增强")
        return image_path
    
    try:
        # 应用多尺度一致性处理
        result_path = apply_multi_scale_consistency(image_path, config)
        
        logger.info(f"✅ 多尺度增强完成：{result_path}")
        return result_path
        
    except Exception as e:
        logger.error(f"❌ 多尺度增强失败：{e}")
        return image_path


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 multi_scale.py <图片路径> [输出路径]")
        print("示例：python3 multi_scale.py input.jpg output.jpg")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    print("\n🚀 开始多尺度增强...")
    result_path = multi_scale_enhance(input_path)
    print(f"✅ 输出：{result_path}")
