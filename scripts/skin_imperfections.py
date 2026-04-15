#!/usr/bin/env python3
"""
skin_imperfections.py - 皮肤瑕疵添加模块

基于《AI 图片识别技术深度研究报告》实现皮肤瑕疵添加技术。
AI 生成图像的皮肤过于完美，缺少真实皮肤的微小瑕疵。

功能：
1. 添加微小痣/斑点
2. 添加细纹/皱纹
3. 添加毛孔纹理
4. 添加肤色不均匀

使用方式：
    from skin_imperfections import add_skin_imperfections
    add_skin_imperfections('input.jpg', config)
"""

import os
import numpy as np
from pathlib import Path
from typing import Optional, Dict
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


def add_moles(image_path: str, density: float = 0.3) -> str:
    """
    添加微小痣/斑点
    
    Args:
        image_path: 输入图片路径
        density: 痣的密度 (0.1-0.5 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        h, w = img_array.shape[:2]
        
        # 随机生成痣的位置
        num_moles = int(density * (h * w) / 10000)  # 每 10000 像素添加 density 个痣
        
        for _ in range(num_moles):
            x = np.random.randint(0, w)
            y = np.random.randint(0, h)
            
            # 痣的大小（1-3 像素）
            size = np.random.randint(1, 4)
            
            # 痣的颜色（深棕色）
            color = np.array([
                np.random.uniform(80, 120),
                np.random.uniform(60, 100),
                np.random.uniform(50, 90)
            ])
            
            # 添加痣
            for dy in range(-size, size + 1):
                for dx in range(-size, size + 1):
                    if 0 <= y + dy < h and 0 <= x + dx < w:
                        dist = np.sqrt(dx**2 + dy**2)
                        if dist <= size:
                            alpha = 1 - dist / size  # 边缘渐变
                            img_array[y + dy, x + dx] = img_array[y + dy, x + dx] * (1 - alpha * 0.5) + color * alpha * 0.5
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_moles.jpg'
        result = np.clip(img_array, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 痣/斑点添加完成 (数量={num_moles})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 痣/斑点添加失败：{e}")
        return image_path


def add_fine_lines(image_path: str, intensity: float = 0.1) -> str:
    """
    添加细纹/皱纹
    
    Args:
        image_path: 输入图片路径
        intensity: 细纹强度 (0.05-0.2 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        from scipy.ndimage import gaussian_filter
        
        img = Image.open(image_path).convert('L')  # 灰度图处理
        img_array = np.array(img, dtype=np.float32)
        
        h, w = img_array.shape
        
        # 生成细纹图案
        lines = np.zeros_like(img_array)
        
        # 随机生成细纹
        num_lines = int(intensity * (h + w) / 2)
        
        for _ in range(num_lines):
            # 随机起点和终点
            x1, y1 = np.random.randint(0, w), np.random.randint(0, h)
            x2 = x1 + np.random.randint(-50, 50)
            y2 = y1 + np.random.randint(-50, 50)
            
            # 画线
            length = int(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))
            for i in range(length):
                t = i / length
                x = int(x1 + t * (x2 - x1))
                y = int(y1 + t * (y2 - y1))
                if 0 <= x < w and 0 <= y < h:
                    # 细纹强度（负值，让皮肤变暗）
                    lines[y, x] -= np.random.uniform(5, 15) * intensity
        
        # 模糊细纹，使其更自然
        lines = gaussian_filter(lines, sigma=1.0)
        
        # 添加到原图
        result = img_array + lines
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_lines.jpg'
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 细纹/皱纹添加完成 (数量={num_lines})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 细纹/皱纹添加失败：{e}")
        return image_path


def add_pores(image_path: str, intensity: float = 0.05) -> str:
    """
    添加毛孔纹理
    
    Args:
        image_path: 输入图片路径
        intensity: 毛孔强度 (0.02-0.1 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        h, w = img_array.shape[:2]
        
        # 生成毛孔噪声（高频噪声）
        np.random.seed(42)  # 固定种子，使纹理可重复
        pore_noise = np.random.randn(h, w) * intensity * 10
        
        # 模糊一点，使毛孔更自然
        from scipy.ndimage import gaussian_filter
        pore_noise = gaussian_filter(pore_noise, sigma=0.5)
        
        # 添加到每个通道
        for c in range(3):
            img_array[:, :, c] += pore_noise
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_pores.jpg'
        result = np.clip(img_array, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 毛孔纹理添加完成 (强度={intensity})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 毛孔纹理添加失败：{e}")
        return image_path


def add_skin_tone_variation(image_path: str, intensity: float = 0.03) -> str:
    """
    添加肤色不均匀
    
    Args:
        image_path: 输入图片路径
        intensity: 肤色变化强度 (0.01-0.05 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        from scipy.ndimage import gaussian_filter
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)
        
        h, w = img_array.shape[:2]
        
        # 生成低频肤色变化
        variation = np.random.randn(h, w) * intensity
        
        # 大幅模糊，创建大区域的肤色变化
        variation = gaussian_filter(variation, sigma=20)
        
        # 添加到红色通道（影响肤色）
        img_array[:, :, 0] += variation * 20
        img_array[:, :, 1] += variation * 10
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_tone.jpg'
        result = np.clip(img_array, 0, 255).astype(np.uint8)
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 肤色不均匀添加完成 (强度={intensity})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 肤色不均匀添加失败：{e}")
        return image_path


def add_skin_imperfections(image_path: str, config: Optional[Dict] = None) -> str:
    """
    皮肤瑕疵添加主函数
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - add_moles: 是否添加痣 (默认 True)
            - mole_density: 痣密度 (默认 0.3)
            - add_fine_lines: 是否添加细纹 (默认 True)
            - lines_intensity: 细纹强度 (默认 0.1)
            - add_pores: 是否添加毛孔 (默认 True)
            - pores_intensity: 毛孔强度 (默认 0.05)
            - add_tone_variation: 是否添加肤色变化 (默认 True)
            - tone_intensity: 肤色变化强度 (默认 0.03)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'add_moles': True,
        'mole_density': 0.3,
        'add_fine_lines': True,
        'lines_intensity': 0.1,
        'add_pores': True,
        'pores_intensity': 0.05,
        'add_tone_variation': True,
        'tone_intensity': 0.03,
    }
    
    config = {**default_config, **(config or {})}
    
    # 检查依赖
    if not check_dependencies():
        logger.warning("⚠️ 依赖缺失，跳过皮肤瑕疵添加")
        return image_path
    
    try:
        current_path = image_path
        
        # 步骤 1: 添加毛孔
        if config.get('add_pores', True):
            current_path = add_pores(current_path, intensity=config.get('pores_intensity', 0.05))
        
        # 步骤 2: 添加肤色变化
        if config.get('add_tone_variation', True):
            current_path = add_skin_tone_variation(current_path, intensity=config.get('tone_intensity', 0.03))
        
        # 步骤 3: 添加痣
        if config.get('add_moles', True):
            current_path = add_moles(current_path, density=config.get('mole_density', 0.3))
        
        # 步骤 4: 添加细纹
        if config.get('add_fine_lines', True):
            current_path = add_fine_lines(current_path, intensity=config.get('lines_intensity', 0.1))
        
        logger.info(f"✅ 皮肤瑕疵添加完成：{current_path}")
        return current_path
        
    except Exception as e:
        logger.error(f"❌ 皮肤瑕疵添加失败：{e}")
        return image_path


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 skin_imperfections.py <图片路径> [输出路径]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    print("\n🎨 开始皮肤瑕疵添加...")
    result_path = add_skin_imperfections(input_path)
    print(f"✅ 输出：{result_path}")
