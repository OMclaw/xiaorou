#!/usr/bin/env python3
"""
patch_texture.py - 局部纹理一致性模块

基于《AI 图片识别技术深度研究报告》实现补丁级纹理优化技术。
AI 生成图像在局部补丁和全局纹理上常有不一致性。

功能：
1. 重叠补丁提取 - 避免边界痕迹
2. 补丁纹理优化 - 在每个补丁上优化纹理
3. 无缝融合 - 泊松融合或羽化边缘

使用方式：
    from patch_texture import patch_texture_optimization
    patch_texture_optimization('input.jpg', patch_size=64)
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


def extract_patches(image: np.ndarray, patch_size: int = 64, stride: int = 32) -> List[Tuple[np.ndarray, int, int]]:
    """
    提取重叠补丁
    
    Args:
        image: 输入图像数组 (H, W, C)
        patch_size: 补丁大小 (默认 64)
        stride: 步长 (默认 32，重叠 50%)
    
    Returns:
        补丁列表，每个元素为 (patch, y, x)
    """
    patches = []
    h, w = image.shape[:2]
    
    for y in range(0, h - patch_size + 1, stride):
        for x in range(0, w - patch_size + 1, stride):
            patch = image[y:y+patch_size, x:x+patch_size]
            patches.append((patch, y, x))
    
    # 处理边界
    if h % stride != 0:
        for x in range(0, w - patch_size + 1, stride):
            y = h - patch_size
            patch = image[y:y+patch_size, x:x+patch_size]
            patches.append((patch, y, x))
    
    if w % stride != 0:
        for y in range(0, h - patch_size + 1, stride):
            x = w - patch_size
            patch = image[y:y+patch_size, x:x+patch_size]
            patches.append((patch, y, x))
    
    # 右下角
    if h % stride != 0 and w % stride != 0:
        y, x = h - patch_size, w - patch_size
        patch = image[y:y+patch_size, x:x+patch_size]
        patches.append((patch, y, x))
    
    return patches


def optimize_patch_texture(patch: np.ndarray, strength: float = 0.1) -> np.ndarray:
    """
    优化单个补丁的纹理
    
    技术原理：
    - 应用轻微的纹理正则化
    - 减少 AI 生成的纹理不一致性
    - 保持主要结构，优化细节纹理
    
    Args:
        patch: 补丁图像数组
        strength: 优化强度 (0.05-0.2 推荐)
    
    Returns:
        优化后的补丁
    """
    try:
        from scipy.ndimage import gaussian_filter, median_filter
        
        patch_float = patch.astype(np.float32)
        
        # 方法 1: 轻微的中值滤波（保持边缘）
        median_filtered = median_filter(patch_float, size=3)
        
        # 方法 2: 轻微的高斯模糊
        gaussian_filtered = gaussian_filter(patch_float, sigma=0.5)
        
        # 混合原始和滤波结果
        optimized = patch_float * (1 - strength) + median_filtered * strength * 0.5 + gaussian_filtered * strength * 0.5
        
        # 裁剪到有效范围
        optimized = np.clip(optimized, 0, 255).astype(np.uint8)
        
        return optimized
        
    except Exception as e:
        logger.warning(f"⚠️ 补丁纹理优化失败：{e}")
        return patch


def create_feather_mask(patch_size: int, feather_radius: int = 8) -> np.ndarray:
    """
    创建羽化掩码（用于无缝融合）
    
    Args:
        patch_size: 补丁大小
        feather_radius: 羽化半径
    
    Returns:
        羽化掩码数组
    """
    mask = np.ones((patch_size, patch_size), dtype=np.float32)
    
    # 创建距离图
    y, x = np.ogrid[:patch_size, :patch_size]
    center = patch_size // 2
    
    # 计算到边缘的距离
    dist_to_edge = np.minimum(np.minimum(x, patch_size - 1 - x), 
                              np.minimum(y, patch_size - 1 - y))
    
    # 羽化区域
    feather_mask = np.clip(dist_to_edge / feather_radius, 0, 1)
    
    return feather_mask


def fuse_patches_seamlessly(patches: List[Tuple[np.ndarray, int, int]], 
                            image_size: Tuple[int, int], 
                            channels: int = 3) -> np.ndarray:
    """
    无缝融合补丁
    
    Args:
        patches: 补丁列表 (patch, y, x)
        image_size: 输出图像尺寸 (H, W)
        channels: 通道数
    
    Returns:
        融合后的图像
    """
    h, w = image_size
    result = np.zeros((h, w, channels), dtype=np.float32)
    weight_sum = np.zeros((h, w), dtype=np.float32)
    
    patch_size = patches[0][0].shape[0]
    feather_mask = create_feather_mask(patch_size)
    
    for patch, y, x in patches:
        # 如果是灰度图，扩展羽化掩码
        if patch.ndim == 2:
            mask = feather_mask
        else:
            mask = np.stack([feather_mask] * patch.shape[2], axis=-1)
        
        # 加权融合
        result[y:y+patch_size, x:x+patch_size] += patch.astype(np.float32) * mask
        weight_sum[y:y+patch_size, x:x+patch_size] += feather_mask
    
    # 归一化
    weight_sum = np.stack([weight_sum] * channels, axis=-1)
    weight_sum = np.maximum(weight_sum, 1e-10)  # 避免除零
    
    result = result / weight_sum
    result = np.clip(result, 0, 255).astype(np.uint8)
    
    return result


def patch_texture_optimization(image_path: str, config: Optional[Dict] = None) -> str:
    """
    补丁纹理优化主函数
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - patch_size: 补丁大小 (默认 64)
            - stride: 步长 (默认 32)
            - optimization_strength: 优化强度 (默认 0.1)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'patch_size': 64,
        'stride': 32,
        'optimization_strength': 0.1,
    }
    
    config = {**default_config, **(config or {})}
    config['patch_size'] = int(os.environ.get('XIAOROU_PATCH_SIZE', config['patch_size']))
    config['stride'] = int(os.environ.get('XIAOROU_PATCH_STRIDE', config['stride']))
    
    try:
        from PIL import Image
        
        # 读取图片
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        patch_size = config.get('patch_size', 64)
        stride = config.get('stride', 32)
        strength = config.get('optimization_strength', 0.1)
        
        # 提取补丁
        patches = extract_patches(img_array, patch_size=patch_size, stride=stride)
        
        # 优化每个补丁
        optimized_patches = []
        for patch, y, x in patches:
            optimized = optimize_patch_texture(patch, strength=strength)
            optimized_patches.append((optimized, y, x))
        
        # 无缝融合
        result = fuse_patches_seamlessly(optimized_patches, (img_array.shape[0], img_array.shape[1]), img_array.shape[2] if img_array.ndim == 3 else 1)
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_patch_texture.jpg'
        if result.ndim == 3 and result.shape[2] == 1:
            result = result[:, :, 0]
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 补丁纹理优化完成 (patch_size={patch_size}, stride={stride})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 补丁纹理优化失败：{e}")
        return image_path


def texture_consistency_check(image_path: str) -> Dict:
    """
    纹理一致性检查（用于调试）
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        纹理一致性指标
    """
    try:
        from PIL import Image
        from scipy.ndimage import sobel
        
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)
        
        # 计算梯度
        grad_x = sobel(img_array, axis=1)
        grad_y = sobel(img_array, axis=0)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        # 纹理均匀性指标
        texture_uniformity = 1.0 / (np.std(gradient_magnitude) + 1e-10)
        
        # 边缘清晰度
        edge_sharpness = np.mean(gradient_magnitude)
        
        return {
            'texture_uniformity': texture_uniformity,
            'edge_sharpness': edge_sharpness,
            'gradient_std': np.std(gradient_magnitude),
        }
        
    except Exception as e:
        logger.error(f"❌ 纹理一致性检查失败：{e}")
        return {}


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 patch_texture.py <图片路径> [输出路径]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    print("\n📊 原始纹理特征:")
    features = texture_consistency_check(input_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
    
    print("\n🚀 开始补丁纹理优化...")
    result_path = patch_texture_optimization(input_path)
    print(f"✅ 输出：{result_path}")
    
    print("\n📊 优化后纹理特征:")
    features = texture_consistency_check(result_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
