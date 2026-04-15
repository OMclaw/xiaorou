#!/usr/bin/env python3
"""
edge_naturalization.py - 边缘自然化模块

基于《AI 图片识别技术深度研究报告》实现边缘自然化技术。
AI 生成图像的边缘常过于锐利或不自然。

功能：
1. 自适应边缘检测 - Canny/Sobel
2. 边缘自然化处理 - 边缘区域自适应模糊
3. 边缘感知滤波 - 双边滤波保持边缘

使用方式：
    from edge_naturalization import edge_aware_filtering
    edge_aware_filtering('input.jpg')
"""

import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple
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


def detect_edges_adaptive(image: np.ndarray, method: str = 'sobel') -> np.ndarray:
    """
    自适应边缘检测
    
    Args:
        image: 输入图像数组 (H, W) 或 (H, W, C)
        method: 检测方法
                - 'sobel': Sobel 算子
                - 'canny': Canny 边缘（需要 opencv）
                - 'laplacian': Laplacian 边缘
    
    Returns:
        边缘图 (H, W) 浮点数组
    """
    # 转换为灰度图
    if image.ndim == 3:
        gray = np.mean(image, axis=2).astype(np.float32)
    else:
        gray = image.astype(np.float32)
    
    try:
        if method == 'sobel':
            from scipy.ndimage import sobel
            
            # Sobel 边缘检测
            grad_x = sobel(gray, axis=1)
            grad_y = sobel(gray, axis=0)
            edges = np.sqrt(grad_x**2 + grad_y**2)
            
            # 归一化到 [0, 1]
            edges = edges / (np.max(edges) + 1e-10)
            
        elif method == 'laplacian':
            from scipy.ndimage import laplace
            
            # Laplacian 边缘
            edges = np.abs(laplace(gray))
            edges = edges / (np.max(edges) + 1e-10)
            
        elif method == 'canny':
            try:
                import cv2
                # Canny 边缘检测
                edges = cv2.Canny(gray.astype(np.uint8), 50, 150)
                edges = edges.astype(np.float32) / 255.0
            except ImportError:
                logger.warning("⚠️ OpenCV 未安装，使用 Sobel 代替")
                return detect_edges_adaptive(image, method='sobel')
        else:
            from scipy.ndimage import sobel
            grad_x = sobel(gray, axis=1)
            grad_y = sobel(gray, axis=0)
            edges = np.sqrt(grad_x**2 + grad_y**2)
            edges = edges / (np.max(edges) + 1e-10)
        
        return edges
        
    except Exception as e:
        logger.error(f"❌ 边缘检测失败：{e}")
        return np.zeros_like(gray)


def naturalize_edges(image: np.ndarray, edge_map: np.ndarray, 
                     blur_strength: float = 0.3) -> np.ndarray:
    """
    边缘自然化处理
    
    技术原理：
    - AI 图边缘过于锐利
    - 在边缘区域应用自适应模糊
    - 保持非边缘区域的清晰度
    
    Args:
        image: 输入图像数组
        edge_map: 边缘图 (H, W)
        blur_strength: 模糊强度 (0.1-0.5 推荐)
    
    Returns:
        自然化后的图像
    """
    try:
        from scipy.ndimage import gaussian_filter, bilateral_filter
        
        image_float = image.astype(np.float32)
        
        # 创建边缘感知的模糊核
        # 边缘强的地方模糊强，边缘弱的地方模糊弱
        blur_map = edge_map * blur_strength
        
        # 应用双边滤波（保持边缘）
        try:
            # scipy 的 bilateral_filter 可能需要较新版本
            filtered = bilateral_filter(image_float, sigma_color=0.1 * 255, sigma_spatial=2.0)
        except:
            # fallback: 高斯滤波
            filtered = gaussian_filter(image_float, sigma=0.8)
        
        # 混合原始和滤波结果
        # 边缘区域更多使用滤波结果
        blend_map = np.stack([blur_map] * image_float.shape[2], axis=-1) if image_float.ndim == 3 else blur_map
        blend_map = np.clip(blend_map, 0, 1)
        
        result = image_float * (1 - blend_map) + filtered * blend_map
        
        # 裁剪到有效范围
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 边缘自然化失败：{e}")
        return image


def edge_aware_filtering(image_path: str, config: Optional[Dict] = None) -> str:
    """
    边缘感知滤波主函数
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - edge_method: 边缘检测方法 (默认 'sobel')
            - blur_strength: 模糊强度 (默认 0.3)
            - enable_bilateral: 是否使用双边滤波 (默认 True)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'edge_method': 'sobel',
        'blur_strength': 0.3,
        'enable_bilateral': True,
    }
    
    config = {**default_config, **(config or {})}
    config['blur_strength'] = float(os.environ.get('XIAOROU_EDGE_BLUR_STRENGTH', config['blur_strength']))
    
    try:
        from PIL import Image
        
        # 读取图片
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # 边缘检测
        edge_map = detect_edges_adaptive(img_array, method=config.get('edge_method', 'sobel'))
        
        # 边缘自然化
        result = naturalize_edges(
            img_array, 
            edge_map, 
            blur_strength=config.get('blur_strength', 0.3)
        )
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_edge_natural.jpg'
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 边缘自然化完成 (method={config.get('edge_method')}, blur={config.get('blur_strength')})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 边缘感知滤波失败：{e}")
        return image_path


def edge_sharpness_analysis(image_path: str) -> Dict:
    """
    边缘锐度分析（用于调试）
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        边缘锐度指标
    """
    try:
        from PIL import Image
        from scipy.ndimage import sobel
        
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)
        
        # Sobel 边缘
        grad_x = sobel(img_array, axis=1)
        grad_y = sobel(img_array, axis=0)
        gradient = np.sqrt(grad_x**2 + grad_y**2)
        
        # 边缘强度统计
        edge_strength_mean = np.mean(gradient)
        edge_strength_std = np.std(gradient)
        edge_strength_max = np.max(gradient)
        
        # 边缘密度（强边缘像素比例）
        threshold = 0.5 * edge_strength_max
        edge_density = np.sum(gradient > threshold) / gradient.size
        
        # 边缘连续性（简单指标：边缘像素的连通性）
        # 这里简化为边缘梯度的局部方差
        from scipy.ndimage import uniform_filter
        local_mean = uniform_filter(gradient, size=5)
        local_var = np.mean((gradient - local_mean) ** 2)
        
        return {
            'edge_strength_mean': edge_strength_mean,
            'edge_strength_std': edge_strength_std,
            'edge_strength_max': edge_strength_max,
            'edge_density': edge_density,
            'edge_continuity': 1.0 / (local_var + 1e-10),
        }
        
    except Exception as e:
        logger.error(f"❌ 边缘锐度分析失败：{e}")
        return {}


def edge_naturalize_enhance(image_path: str, config: Optional[Dict] = None) -> str:
    """
    边缘自然化增强主函数
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
    
    Returns:
        输出图片路径
    """
    # 检查依赖
    if not check_dependencies():
        logger.warning("⚠️ 依赖缺失，跳过边缘自然化")
        return image_path
    
    # 边缘感知滤波
    return edge_aware_filtering(image_path, config)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 edge_naturalization.py <图片路径> [输出路径]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    print("\n📊 原始边缘特征:")
    features = edge_sharpness_analysis(input_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
    
    print("\n🚀 开始边缘自然化...")
    result_path = edge_naturalize_enhance(input_path)
    print(f"✅ 输出：{result_path}")
    
    print("\n📊 优化后边缘特征:")
    features = edge_sharpness_analysis(result_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
