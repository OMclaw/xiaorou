#!/usr/bin/env python3.11
"""postprocess.py - 图片后处理模块

添加真实相机特征，减少 AI 生成痕迹：
- PRNU 传感器噪声
- ISO 噪点
- JPEG 压缩伪影
- 轻微镜头畸变
- 色彩微调

用法:
    python3 postprocess.py input.jpg output.jpg
"""

import cv2
import numpy as np
import sys
import os
from pathlib import Path
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def add_prnu_noise(image: np.ndarray, strength: float = 0.008) -> np.ndarray:
    """
    添加 PRNU (光响应非均匀性) 噪声 - 模拟相机传感器特征
    
    Args:
        image: 输入图片 (BGR 格式)
        strength: PRNU 强度 (0.005-0.012 推荐)
    
    Returns:
        添加 PRNU 噪声后的图片
    """
    prnu = np.random.normal(0, strength, image.shape)
    result = image * (1 + prnu)
    return np.clip(result, 0, 255).astype(np.uint8)


def add_iso_noise(image: np.ndarray, iso: int = 400, strength: float = 1.5) -> np.ndarray:
    """
    添加 ISO 噪点 - 模拟高感光度颗粒
    
    Args:
        image: 输入图片
        iso: ISO 值 (100-3200)
        strength: 噪点强度
    
    Returns:
        添加 ISO 噪点后的图片
    """
    # ISO 越高，噪点越多
    iso_factor = iso / 400.0
    noise = np.random.normal(0, strength * iso_factor, image.shape)
    result = image + noise
    return np.clip(result, 0, 255).astype(np.uint8)


def add_jpeg_compression(image: np.ndarray, quality: int = 88) -> np.ndarray:
    """
    添加 JPEG 压缩伪影 - 模拟真实相机输出
    
    Args:
        image: 输入图片
        quality: JPEG 质量 (75-95 推荐，越低压缩越明显)
    
    Returns:
        JPEG 压缩后的图片
    """
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encoded = cv2.imencode('.jpg', image, encode_param)
    result = cv2.imdecode(encoded, 1)
    return result


def add_lens_distortion(image: np.ndarray, strength: float = 0.00008) -> np.ndarray:
    """
    添加极轻微桶形畸变 - 模拟真实镜头
    
    Args:
        image: 输入图片
        strength: 畸变强度 (0.00005-0.00015 推荐，更保守)
    
    Returns:
        畸变后的图片
    """
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    
    # 创建映射表
    map_x, map_y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = map_x.astype(np.float32)
    map_y = map_y.astype(np.float32)
    
    # 桶形畸变公式
    dx = (map_x - center[0]) * strength * ((map_x - center[0])**2 + (map_y - center[1])**2)
    dy = (map_y - center[1]) * strength * ((map_x - center[0])**2 + (map_y - center[1])**2)
    
    map_x_distorted = map_x + dx
    map_y_distorted = map_y + dy
    
    # 应用畸变
    result = cv2.remap(image, map_x_distorted, map_y_distorted, cv2.INTER_LINEAR)
    return result


def add_chromatic_aberration(image: np.ndarray, strength: int = 0) -> np.ndarray:
    """
    添加极轻微色差 - 模拟镜头色散
    
    Args:
        image: 输入图片 (BGR 格式)
        strength: 色差强度 (0=关闭，1-2=轻微)
    
    Returns:
        添加色差后的图片
    """
    if strength <= 0:
        return image.copy()
    
    b, g, r = cv2.split(image)
    
    # 红色通道轻微偏移
    r_shifted = np.roll(r, strength, axis=1)
    # 蓝色通道反向偏移
    b_shifted = np.roll(b, -strength, axis=1)
    
    result = cv2.merge([b_shifted, g, r_shifted])
    return result


def add_vignette(image: np.ndarray, strength: float = 0.3) -> np.ndarray:
    """
    添加暗角效果 - 模拟真实镜头边缘失光
    
    Args:
        image: 输入图片
        strength: 暗角强度 (0.1-0.5 推荐)
    
    Returns:
        添加暗角后的图片
    """
    h, w = image.shape[:2]
    
    # 创建渐变遮罩
    x = np.linspace(-1, 1, w)
    y = np.linspace(-1, 1, h)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)
    
    # 暗角遮罩 (中心亮，边缘暗)
    vignette_mask = 1 - strength * (R ** 2)
    vignette_mask = np.clip(vignette_mask, 0, 1)
    vignette_mask = vignette_mask.astype(np.float32)
    
    # 应用遮罩到每个通道
    result = image * vignette_mask[:, :, np.newaxis]
    return np.clip(result, 0, 255).astype(np.uint8)


def add_film_grain(image: np.ndarray, strength: float = 2.0) -> np.ndarray:
    """
    添加胶片颗粒 - 模拟 Kodak Portra 400 胶片质感
    
    Args:
        image: 输入图片
        strength: 颗粒强度
    
    Returns:
        添加胶片颗粒后的图片
    """
    # 生成彩色噪声
    grain = np.random.normal(0, strength, image.shape)
    result = image + grain
    return np.clip(result, 0, 255).astype(np.uint8)


def realistic_postprocess(
    input_path: str,
    output_path: Optional[str] = None,
    config: dict = None
) -> str:
    """
    完整的真实感后处理流程
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径 (不填则自动生成)
        config: 处理配置字典
    
    Returns:
        输出图片路径
    """
    # 默认配置 (P0 优化 - 纯净画质，无光点/噪点/颗粒)
    if config is None:
        config = {
            'prnu_strength': 0,          # ✅ 关闭 PRNU (无光点)
            'iso': 100,                  # ISO 100
            'iso_strength': 0,           # ✅ 关闭 ISO 噪点 (无光点)
            'jpeg_quality': 98,          # ↑ JPEG 质量 98% (极少压缩)
            'lens_distortion': 0,        # ✅ 关闭镜头畸变
            'chromatic_aberration': 0,   # ✅ 关闭色差
            'vignette_strength': 0,      # ✅ 关闭暗角
            'film_grain': 0,             # ✅ 关闭胶片颗粒 (无光点)
        }
    
    # 读取图片
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"无法读取图片：{input_path}")
    
    logger.info(f"📷 开始真实感后处理：{input_path}")
    
    # 1. 添加 PRNU 传感器噪声
    image = add_prnu_noise(image, config.get('prnu_strength', 0.008))
    logger.info("  ✓ 添加 PRNU 传感器噪声")
    
    # 2. 添加 ISO 噪点
    image = add_iso_noise(image, config.get('iso', 400), config.get('iso_strength', 1.5))
    logger.info(f"  ✓ 添加 ISO {config.get('iso', 400)} 噪点")
    
    # 3. 添加胶片颗粒
    image = add_film_grain(image, config.get('film_grain', 1.8))
    logger.info("  ✓ 添加胶片颗粒")
    
    # 4. 添加轻微镜头畸变
    image = add_lens_distortion(image, config.get('lens_distortion', 0.0003))
    logger.info("  ✓ 添加镜头畸变")
    
    # 5. 添加轻微色差
    image = add_chromatic_aberration(image, config.get('chromatic_aberration', 1))
    logger.info("  ✓ 添加色差")
    
    # 6. 添加暗角
    image = add_vignette(image, config.get('vignette_strength', 0.25))
    logger.info("  ✓ 添加暗角效果")
    
    # 7. JPEG 压缩 (最后一步)
    image = add_jpeg_compression(image, config.get('jpeg_quality', 88))
    logger.info(f"  ✓ JPEG 压缩 (质量 {config.get('jpeg_quality', 88)}%)")
    
    # 生成输出路径
    if output_path is None:
        input_p = Path(input_path)
        output_path = str(input_p.parent / f"{input_p.stem}_realistic{input_p.suffix}")
    
    # 保存图片
    cv2.imwrite(output_path, image)
    logger.info(f"✅ 后处理完成：{output_path}")
    
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 postprocess.py input.jpg [output.jpg]")
        print("\n可选环境变量:")
        print("  PRNU_STRENGTH=0.008      PRNU 噪声强度")
        print("  ISO=400                  ISO 值")
        print("  JPEG_QUALITY=88          JPEG 质量")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 从环境变量读取配置
    config = {
        'prnu_strength': float(os.environ.get('PRNU_STRENGTH', '0.008')),
        'iso': int(os.environ.get('ISO', '400')),
        'iso_strength': float(os.environ.get('ISO_STRENGTH', '1.5')),
        'jpeg_quality': int(os.environ.get('JPEG_QUALITY', '88')),
        'lens_distortion': float(os.environ.get('LENS_DISTORTION', '0.0003')),
        'chromatic_aberration': int(os.environ.get('CHROMATIC_ABERRATION', '1')),
        'vignette_strength': float(os.environ.get('VIGNETTE', '0.25')),
        'film_grain': float(os.environ.get('FILM_GRAIN', '1.8')),
    }
    
    try:
        result_path = realistic_postprocess(input_file, output_file, config)
        print(f"✅ 处理完成：{result_path}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ 处理失败：{e}")
        sys.exit(1)
