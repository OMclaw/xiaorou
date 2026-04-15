#!/usr/bin/env python3
"""
postprocess.py - AI 图片后处理模块

基于"如何让 AI 生成图片更真实"洞察文章优化：
- 频域优化：添加 1/f 噪声、模拟相机 ISP
- 空间域优化：轻微模糊 + 锐化
- 元数据处理：清除生成痕迹、添加 EXIF

使用方式：
    from postprocess import enhance_realism
    enhance_realism('input.jpg', 'output.jpg')
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple

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


def add_jpeg_compression(image_path: str, quality: int = 90) -> str:
    """
    添加 JPEG 压缩痕迹（模拟真实相机输出）
    
    Args:
        image_path: 输入图片路径
        quality: JPEG 质量 (85-95 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        # 打开图片
        img = Image.open(image_path)
        
        # 转换为 RGB（如果需要）
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 保存为 JPEG
        output_path = image_path.rsplit('.', 1)[0] + '_jpeg.jpg'
        img.save(output_path, 'JPEG', quality=quality, optimize=True, progressive=True)
        
        logger.info(f"✅ JPEG 压缩完成 (质量：{quality}%)")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ JPEG 压缩失败：{e}")
        return image_path


def add_gaussian_blur(image_path: str, radius: float = 0.3) -> str:
    """
    添加轻微高斯模糊（模拟镜头光学特性）
    
    Args:
        image_path: 输入图片路径
        radius: 模糊半径 (0.3-0.5 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image, ImageFilter
        
        img = Image.open(image_path)
        
        # 应用高斯模糊
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        
        output_path = image_path.rsplit('.', 1)[0] + '_blur.jpg'
        blurred.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 高斯模糊完成 (半径：{radius})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 高斯模糊失败：{e}")
        return image_path


def add_sharpening(image_path: str, strength: float = 0.15) -> str:
    """
    添加轻微锐化（增强细节）
    
    Args:
        image_path: 输入图片路径
        strength: 锐化强度 (0.1-0.2 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image, ImageEnhance
        
        img = Image.open(image_path)
        
        # 应用锐化
        enhancer = ImageEnhance.Sharpness(img)
        sharpened = enhancer.enhance(1.0 + strength)
        
        output_path = image_path.rsplit('.', 1)[0] + '_sharp.jpg'
        sharpened.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 锐化完成 (强度：{strength*100:.0f}%)")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 锐化失败：{e}")
        return image_path


def add_film_grain(image_path: str, iso: int = 300) -> str:
    """
    添加胶片颗粒（模拟真实相机传感器噪声）
    
    Args:
        image_path: 输入图片路径
        iso: ISO 感光度 (200-400 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path)
        img_array = np.array(img)
        
        # 根据 ISO 计算颗粒强度
        grain_strength = (iso - 100) / 300.0  # ISO 200=0.33, ISO 400=1.0
        
        # 生成高斯噪声
        noise = np.random.normal(0, grain_strength * 10, img_array.shape)
        
        # 添加噪声
        noisy_array = img_array + noise
        noisy_array = np.clip(noisy_array, 0, 255).astype(np.uint8)
        
        # 保存
        noisy_img = Image.fromarray(noisy_array)
        output_path = image_path.rsplit('.', 1)[0] + '_grain.jpg'
        noisy_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 胶片颗粒完成 (ISO: {iso})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 胶片颗粒失败：{e}")
        return image_path


def add_vignette(image_path: str, intensity: float = 0.15) -> str:
    """
    添加轻微暗角（模拟镜头特性）
    
    Args:
        image_path: 输入图片路径
        intensity: 暗角强度 (0.1-0.2 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # 创建暗角渐变
        h, w = img_array.shape[:2]
        y, x = np.ogrid[:h, :w]
        
        # 计算到中心的距离（归一化）
        center_x, center_y = w / 2, h / 2
        max_dist = np.sqrt((w/2)**2 + (h/2)**2)
        dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        dist_normalized = dist / max_dist
        
        # 创建暗角遮罩
        vignette = 1 - (dist_normalized ** 2) * intensity
        vignette = vignette[:, :, np.newaxis]
        
        # 应用暗角
        vignetted_array = (img_array * vignette).astype(np.uint8)
        
        # 保存
        vignetted_img = Image.fromarray(vignetted_array)
        output_path = image_path.rsplit('.', 1)[0] + '_vignette.jpg'
        vignetted_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 暗角完成 (强度：{intensity*100:.0f}%)")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 暗角失败：{e}")
        return image_path


def add_color_grading(image_path: str, warmth: float = 1.05) -> str:
    """
    调整色彩（轻微暖色调）
    
    Args:
        image_path: 输入图片路径
        warmth: 暖色调强度 (1.0-1.1 推荐，1.0=无变化)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img).astype(np.float32)
        
        # 增加红色和黄色通道（暖色调）
        img_array[:, :, 0] *= warmth  # Red
        img_array[:, :, 1] *= (warmth - 0.02)  # Green (slightly less)
        img_array[:, :, 2] *= (warmth - 0.05)  # Blue (even less)
        
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        
        # 保存
        graded_img = Image.fromarray(img_array)
        output_path = image_path.rsplit('.', 1)[0] + '_graded.jpg'
        graded_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 色彩调整完成 (暖色调：{warmth})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 色彩调整失败：{e}")
        return image_path


def clear_metadata(image_path: str) -> str:
    """
    清除图片元数据（移除生成痕迹）
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        输出图片路径
    """
    try:
        # 方法 1：使用 PIL 重新保存
        from PIL import Image
        
        img = Image.open(image_path)
        
        # 提取 ICC 配置文件（如果有）
        icc_profile = img.info.get('icc_profile')
        
        # 转换为 RGB
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # 保存（不保留元数据）
        output_path = image_path.rsplit('.', 1)[0] + '_clean.jpg'
        img.save(output_path, 'JPEG', quality=95, icc_profile=icc_profile)
        
        logger.info(f"✅ 元数据已清除")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 清除元数据失败：{e}")
        return image_path


def add_exif_metadata(image_path: str, camera_model: str = "iPhone 15 Pro") -> str:
    """
    添加模拟的 EXIF 元数据（使用 Pillow，不需要 exiftool）
    
    Args:
        image_path: 输入图片路径
        camera_model: 相机型号
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        from PIL.ExifTags import Base
        
        img = Image.open(image_path)
        
        # 构建 EXIF 数据
        exif_data = {
            0x010F: 'Apple',  # Make
            0x0110: camera_model,  # Model
            0x0131: 'iOS 17.2',  # Software
            0x8298: 'iPhone 15 Pro back triple camera',  # LensModel
        }
        
        # 添加拍摄时间
        from datetime import datetime
        now = datetime.now().strftime('%Y:%m:%d %H:%M:%S')
        exif_data[0x9003] = now  # DateTimeOriginal
        
        # 保存带 EXIF 的图片
        output_path = image_path.rsplit('.', 1)[0] + '_exif.jpg'
        
        # 转换为 RGB（如果需要）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 保存并添加 EXIF
        img.save(output_path, 'JPEG', quality=95, exif=img.getexif())
        
        # 使用 piexif 库添加更详细的 EXIF（如果可用）
        try:
            import piexif
            exif_dict = {
                "0th": {
                    piexif.ImageIFD.Make: "Apple",
                    piexif.ImageIFD.Model: camera_model,
                    piexif.ImageIFD.Software: "iOS 17.2",
                },
                "Exif": {
                    piexif.ExifIFD.DateTimeOriginal: now,
                    piexif.ExifIFD.LensModel: "iPhone 15 Pro back triple camera",
                },
                "GPS": {
                    piexif.GPSIFD.GPSLatitude: [(31, 1, 0), (14, 1, 0), (1200, 1, 100)],  # 上海
                    piexif.GPSIFD.GPSLongitude: [(121, 1, 0), (29, 1, 0), (3600, 1, 100)],  # 上海
                }
            }
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, output_path)
            logger.info(f"✅ EXIF 元数据已添加 ({camera_model} + GPS)")
        except ImportError:
            logger.info(f"✅ EXIF 元数据已添加 ({camera_model})，安装 piexif 可添加 GPS 信息")
        except Exception as e:
            logger.warning(f"⚠️ EXIF 详细添加失败：{e}")
        
        return output_path
            
    except Exception as e:
        logger.warning(f"⚠️ 添加 EXIF 失败：{e}")
        return image_path


def add_chromatic_aberration(image_path: str, offset: float = 0.5) -> str:
    """
    添加色差效果（RGB 通道轻微偏移，模拟镜头色散）
    
    Args:
        image_path: 输入图片路径
        offset: 通道偏移量 (0.3-1.0 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # 分离 RGB 通道
        r_channel = img_array[:, :, 0]
        g_channel = img_array[:, :, 1]
        b_channel = img_array[:, :, 2]
        
        # 创建偏移
        h, w = img_array.shape[:2]
        offset_int = int(offset)
        
        # R 通道向右上偏移，B 通道向左下偏移
        r_shifted = np.roll(np.roll(r_channel, -offset_int, axis=0), offset_int, axis=1)
        b_shifted = np.roll(np.roll(b_channel, offset_int, axis=0), -offset_int, axis=1)
        
        # 合并通道
        ca_array = np.stack([r_shifted, g_channel, b_shifted], axis=2)
        ca_array = np.clip(ca_array, 0, 255).astype(np.uint8)
        
        # 保存
        ca_img = Image.fromarray(ca_array)
        output_path = image_path.rsplit('.', 1)[0] + '_ca.jpg'
        ca_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 色差效果完成 (偏移：{offset})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 色差效果失败：{e}")
        return image_path


def add_lens_distortion(image_path: str, strength: float = 0.02) -> str:
    """
    添加轻微桶形畸变（模拟真实镜头）
    
    Args:
        image_path: 输入图片路径
        strength: 畸变强度 (0.01-0.05 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        
        # 创建映射表
        center_x, center_y = w / 2, h / 2
        max_dist = max(center_x, center_y)
        
        # 创建输出数组
        distorted = np.zeros_like(img_array)
        
        # 桶形畸变公式
        for y in range(h):
            for x in range(w):
                # 归一化坐标
                nx = (x - center_x) / max_dist
                ny = (y - center_y) / max_dist
                
                # 计算径向距离
                r = np.sqrt(nx**2 + ny**2)
                
                # 应用桶形畸变
                factor = 1 + strength * r**2
                
                # 计算源坐标
                src_x = int(center_x + nx * factor * max_dist)
                src_y = int(center_y + ny * factor * max_dist)
                
                # 边界检查
                if 0 <= src_x < w and 0 <= src_y < h:
                    distorted[y, x] = img_array[src_y, src_x]
                else:
                    distorted[y, x] = img_array[y, x]
        
        # 保存
        distorted_img = Image.fromarray(distorted)
        output_path = image_path.rsplit('.', 1)[0] + '_distort.jpg'
        distorted_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 镜头畸变完成 (强度：{strength*100:.1f}%)")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 镜头畸变失败：{e}")
        return image_path


def add_sensor_dust(image_path: str, density: int = 5) -> str:
    """
    添加传感器灰尘痕迹（微小暗点）
    
    Args:
        image_path: 输入图片路径
        density: 灰尘数量 (3-10 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        
        # 随机生成灰尘位置
        np.random.seed(42)  # 固定种子保证可重现
        for _ in range(density):
            x = np.random.randint(0, w)
            y = np.random.randint(0, h)
            size = np.random.randint(1, 3)
            
            # 创建暗点
            for dy in range(-size, size+1):
                for dx in range(-size, size+1):
                    if 0 <= y+dy < h and 0 <= x+dx < w:
                        # 轻微变暗（模拟灰尘）
                        img_array[y+dy, x+dx] = img_array[y+dy, x+dx] * 0.7
        
        # 保存
        dust_img = Image.fromarray(img_array)
        output_path = image_path.rsplit('.', 1)[0] + '_dust.jpg'
        dust_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 传感器灰尘完成 (数量：{density})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 传感器灰尘失败：{e}")
        return image_path


def add_micro_jitter(image_path: str, amplitude: float = 0.3) -> str:
    """
    添加微抖动模糊（模拟手持拍摄）
    
    Args:
        image_path: 输入图片路径
        amplitude: 抖动幅度 (0.2-0.5 推荐)
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image, ImageFilter
        import numpy as np
        
        img = Image.open(image_path).convert('RGB')
        
        # 创建方向性模糊（模拟抖动）
        # 使用轻微的运动模糊
        kernel = np.zeros((3, 3))
        kernel[1, :] = [amplitude, 1-amplitude*2, amplitude]
        
        # 应用轻微模糊
        jittered = img.filter(ImageFilter.GaussianBlur(radius=amplitude))
        
        output_path = image_path.rsplit('.', 1)[0] + '_jitter.jpg'
        jittered.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 微抖动模糊完成 (幅度：{amplitude})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 微抖动模糊失败：{e}")
        return image_path


def add_complete_exif(image_path: str, camera_model: str = "iPhone 15 Pro") -> str:
    """
    添加完整 EXIF 信息（ISO、光圈、快门、GPS、镜头等）
    
    Args:
        image_path: 输入图片路径
        camera_model: 相机型号
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        from datetime import datetime
        import piexif
        
        img = Image.open(image_path)
        
        # 转换为 RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 拍摄时间
        now = datetime.now().strftime('%Y:%m:%d %H:%M:%S')
        
        # 构建完整 EXIF
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: "Apple",
                piexif.ImageIFD.Model: camera_model,
                piexif.ImageIFD.Software: "iOS 17.2.1",
                piexif.ImageIFD.XResolution: (72, 1),
                piexif.ImageIFD.YResolution: (72, 1),
                piexif.ImageIFD.ResolutionUnit: 2,  # inches
                piexif.ImageIFD.Orientation: 1,
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: now,
                piexif.ExifIFD.DateTimeDigitized: now,
                piexif.ExifIFD.LensModel: "iPhone 15 Pro back triple camera",
                piexif.ExifIFD.LensMake: "Apple",
                piexif.ExifIFD.FNumber: (178, 100),  # f/1.78
                piexif.ExifIFD.ExposureTime: (1, 60),  # 1/60s
                piexif.ExifIFD.ISOSpeedRatings: 100,
                piexif.ExifIFD.ExposureProgram: 2,  # Normal program
                piexif.ExifIFD.MeteringMode: 5,  # Pattern
                piexif.ExifIFD.Flash: 16,  # Flash did not fire
                piexif.ExifIFD.FocalLength: (651, 100),  # 6.51mm
                piexif.ExifIFD.ColorSpace: 1,  # sRGB
                piexif.ExifIFD.ExifVersion: b'0231',
                piexif.ExifIFD.ComponentsConfiguration: b'\x01\x02\x03\x00',
                piexif.ExifIFD.Sharpness: 0,  # Normal
                piexif.ExifIFD.WhiteBalance: 0,  # Auto
                piexif.ExifIFD.SceneCaptureType: 0,  # Standard
            },
            "GPS": {
                piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
                piexif.GPSIFD.GPSLatitudeRef: 'N',
                piexif.GPSIFD.GPSLatitude: [(31, 1, 0), (14, 1, 0), (1200, 1, 100)],  # 上海
                piexif.GPSIFD.GPSLongitudeRef: 'E',
                piexif.GPSIFD.GPSLongitude: [(121, 1, 0), (29, 1, 0), (3600, 1, 100)],  # 上海
                piexif.GPSIFD.GPSAltitudeRef: 0,
                piexif.GPSIFD.GPSAltitude: (10, 1),  # 10m
                piexif.GPSIFD.GPSTimeStamp: [(int(now.split(':')[0]), 1), (int(now.split(':')[1]), 1), (0, 1)],
                piexif.GPSIFD.GPSDateStamp: now.split(' ')[0].replace(':', '-'),
            },
            "1st": {},
            "thumbnail": None,
        }
        
        # 保存输出路径
        output_path = image_path.rsplit('.', 1)[0] + '_complete_exif.jpg'
        
        # 保存带 EXIF 的图片
        exif_bytes = piexif.dump(exif_dict)
        img.save(output_path, 'JPEG', quality=95, exif=exif_bytes)
        
        logger.info(f"✅ 完整 EXIF 已添加 ({camera_model} + ISO/光圈/快门/GPS)")
        return output_path
            
    except ImportError:
        logger.warning("⚠️ piexif 未安装，使用基础 EXIF")
        return add_exif_metadata(image_path, camera_model)
    except Exception as e:
        logger.warning(f"⚠️ 完整 EXIF 添加失败：{e}")
        return add_exif_metadata(image_path, camera_model)


def enhance_realism(input_path: str, output_path: Optional[str] = None, 
                    config: Optional[dict] = None) -> str:
    """
    增强 AI 生成图片的真实感（完整流程 - 终极版）
    
    处理流程：
    1. JPEG 压缩（质量 100%）
    2. 轻微高斯模糊（半径 0.1）
    3. 轻微锐化（强度 5%）
    4. 添加胶片颗粒（ISO 50）
    5. 轻微暗角（强度 5%）
    6. 色彩调整（暖色调 1.01）
    7. 添加色差效果（RGB 通道偏移）
    8. 添加镜头畸变（桶形畸变）
    9. 添加传感器灰尘（微小暗点）
    10. 添加微抖动模糊（手持拍摄模拟）
    11. 清除元数据
    12. 添加完整 EXIF（ISO/光圈/快门/GPS/镜头）
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径（可选，默认自动生成）
        config: 配置字典（可选，覆盖默认参数）
    
    Returns:
        最终输出图片路径
    """
    # 默认配置（全部反 AI 检测技术）
    default_config = {
        # 原始 12 步配置
        'jpeg_quality': 0,            # JPEG 压缩 (0=禁用，不添加压缩痕迹)
        'blur_radius': 0.1,
        'sharp_strength': 0.05,
        'grain_iso': 0,             # 胶片颗粒 ISO (0=禁用，不添加颗粒)
        'vignette_intensity': 0.05,
        'color_warmth': 1.0,        # 暖色调 (1.0=禁用，不调整色彩)
        'ca_offset': 0.0,           # 色差偏移 (0.0=禁用，不添加色差)
        'distortion_strength': 0.02,
        'dust_density': 5,
        'jitter_amplitude': 0.3,
        'camera_model': 'iPhone 15 Pro',
        
        # 🆕 Phase 1: 频域优化 + 对抗扰动
        'frequency_enable': False,       # ❌ 禁用 1/f 频谱噪声
        'spectral_sigma': 0.5,
        'natural_spectrum_strength': 0.0,  # 完全禁用
        'adversarial_enable': True,        # ✅ 启用对抗扰动
        'adversarial_eps': 0.005,          # 低强度
        'subtle_noise_enable': False,      # ❌ 禁用细微噪声
        'subtle_noise_intensity': 0.0,     # 完全禁用
        
        # 🆕 Phase 2: 多尺度 + 纹理一致性（已修复）
        'multi_scale_enable': True,        # ✅ 启用多尺度一致性（已修复）
        'pyramid_levels': 4,
        'patch_texture_enable': True,
        'patch_size': 64,
        
        # 🆕 Phase 3: 皮肤瑕疵 + JPEG 重压缩
        'skin_imperfections_enable': True,  # ✅ 启用皮肤瑕疵
        'skin_mole_density': 0.3,
        'skin_lines_intensity': 0.1,
        'skin_pores_intensity': 0.05,
        'jpeg_recompress_enable': False,     # ❌ 禁用 JPEG 重压缩
        'jpeg_recompress_cycles': 0,
        
        # Phase 4: CLIP 特征 + 边缘自然化
        'clip_optimize_enable': False,  # 可选，计算成本高
        'edge_naturalize_enable': True,
        'edge_blur_strength': 0.3,
    }
    
    # 合并配置
    if config:
        default_config.update(config)
    config = default_config
    
    logger.info("🎨 开始真实性增强处理（全部反 AI 检测技术）...")
    logger.info(f"📁 输入：{input_path}")
    logger.info(f"🔧 当前配置：JPEG 压缩={'禁用' if config.get('jpeg_quality', 0) == 0 else '启用'}, 胶片颗粒={'禁用' if config.get('grain_iso', 50) == 0 else '启用'}, 色彩调整={'禁用' if config.get('color_warmth', 1.0) == 1.0 else '启用'}, 色差效果={'禁用' if config.get('ca_offset', 0.0) == 0.0 else '启用'}, 细微噪声={'禁用' if config.get('subtle_noise_enable', False) == False else '启用'}")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    current_path = os.path.join(temp_dir, 'temp.jpg')
    
    # 复制输入文件到临时目录
    import shutil
    shutil.copy2(input_path, current_path)
    
    # 处理流程（基础步骤 + 反 AI 检测）
    # 原始 12 步（根据配置动态启用/禁用）
    steps = []
    
    # 1️⃣ JPEG 压缩（可选）
    if config.get('jpeg_quality', 0) > 0:
        steps.append(('1️⃣ JPEG 压缩', lambda p: add_jpeg_compression(p, config['jpeg_quality'])))
    else:
        logger.info("ℹ️ JPEG 压缩已禁用")
    
    # 2️⃣-12️⃣ 其他基础步骤（根据配置动态启用/禁用）
    # 2️⃣ 高斯模糊
    steps.append(('2️⃣ 高斯模糊', lambda p: add_gaussian_blur(p, config['blur_radius'])))
    
    # 3️⃣ 锐化
    steps.append(('3️⃣ 锐化', lambda p: add_sharpening(p, config['sharp_strength'])))
    
    # 4️⃣ 胶片颗粒（可选）
    if config.get('grain_iso', 0) > 0:
        steps.append(('4️⃣ 胶片颗粒', lambda p: add_film_grain(p, config['grain_iso'])))
    else:
        logger.info("ℹ️ 胶片颗粒已禁用")
    
    # 5️⃣ 暗角
    steps.append(('5️⃣ 暗角', lambda p: add_vignette(p, config['vignette_intensity'])))
    
    # 6️⃣ 色彩调整（可选）
    if config.get('color_warmth', 1.0) != 1.0:
        steps.append(('6️⃣ 色彩调整', lambda p: add_color_grading(p, config['color_warmth'])))
    else:
        logger.info("ℹ️ 色彩调整已禁用")
    
    # 7️⃣ 色差效果（可选）
    if config.get('ca_offset', 0.0) != 0.0:
        steps.append(('7️⃣ 色差效果', lambda p: add_chromatic_aberration(p, config['ca_offset'])))
    else:
        logger.info("ℹ️ 色差效果已禁用")
    
    # 8️⃣-12️⃣ 其他步骤
    steps.extend([
        ('8️⃣ 镜头畸变', lambda p: add_lens_distortion(p, config['distortion_strength'])),
        ('9️⃣ 传感器灰尘', lambda p: add_sensor_dust(p, config['dust_density'])),
        ('🔟 微抖动模糊', lambda p: add_micro_jitter(p, config['jitter_amplitude'])),
        ('1️⃣1️⃣ 清除元数据', lambda p: clear_metadata(p)),
        ('1️⃣2️⃣ 完整 EXIF', lambda p: add_complete_exif(p, config['camera_model'])),
    ])
    
    # 🆕 反 AI 检测步骤（全部技术）
    # Phase 1: 频域优化 + 对抗扰动（已修复）
    if config.get('frequency_enable', True):
        try:
            from frequency_optimize import frequency_domain_enhance
            steps.append(('🆕 频域优化', lambda p: frequency_domain_enhance(p, {
                'spectral_sigma': config.get('spectral_sigma', 0.5),
                'natural_spectrum_strength': config.get('natural_spectrum_strength', 0.03),
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 频域优化模块未导入：{e}")
    
    if config.get('adversarial_enable', True):
        try:
            from adversarial_noise import adversarial_enhance
            # 只添加对抗扰动，不添加细微噪声
            steps.append(('🆕 对抗扰动', lambda p: adversarial_enhance(p, {
                'adversarial_eps': config.get('adversarial_eps', 0.005),
                'add_subtle_noise': False,  # 禁用细微噪声
                'subtle_noise_intensity': 0.0,
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 对抗扰动模块未导入：{e}")
    else:
        logger.info("ℹ️ 对抗扰动已禁用")
    
    # Phase 2: 多尺度 + 纹理一致性（已修复）
    if config.get('multi_scale_enable', True):
        try:
            from multi_scale import multi_scale_enhance
            steps.append(('🆕 多尺度一致性', lambda p: multi_scale_enhance(p, {
                'pyramid_levels': config.get('pyramid_levels', 4),
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 多尺度模块未导入：{e}")
    
    if config.get('patch_texture_enable', True):
        try:
            from patch_texture import patch_texture_optimization
            steps.append(('🆕 纹理一致性', lambda p: patch_texture_optimization(p, {
                'patch_size': config.get('patch_size', 64),
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 纹理一致性模块未导入：{e}")
    
    # Phase 3: 皮肤瑕疵 + JPEG 重压缩
    if config.get('skin_imperfections_enable', True):
        try:
            from skin_imperfections import add_skin_imperfections
            steps.append(('🆕 皮肤瑕疵', lambda p: add_skin_imperfections(p, {
                'add_moles': True,
                'mole_density': config.get('skin_mole_density', 0.3),
                'add_fine_lines': True,
                'lines_intensity': config.get('skin_lines_intensity', 0.1),
                'add_pores': True,
                'pores_intensity': config.get('skin_pores_intensity', 0.05),
                'add_tone_variation': True,
                'tone_intensity': 0.03,
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 皮肤瑕疵模块未导入：{e}")
    
    if config.get('jpeg_recompress_enable', False):  # 默认禁用
        try:
            from jpeg_recompression import add_jpeg_recompression
            steps.append(('🆕 JPEG 重压缩', lambda p: add_jpeg_recompression(p, {
                'compression_cycles': config.get('jpeg_recompress_cycles', 2),
                'quality_range': [75, 92],
            })))
        except ImportError as e:
            logger.warning(f"⚠️ JPEG 重压缩模块未导入：{e}")
    else:
        logger.info("ℹ️ JPEG 重压缩已禁用")
    
    # Phase 4: 边缘自然化
    if config.get('edge_naturalize_enable', True):
        try:
            from edge_naturalization import edge_naturalize_enhance
            steps.append(('🆕 边缘自然化', lambda p: edge_naturalize_enhance(p, {
                'blur_strength': config.get('edge_blur_strength', 0.3),
            })))
        except ImportError as e:
            logger.warning(f"⚠️ 边缘自然化模块未导入：{e}")
    
    # Phase 3: CLIP 特征优化（可选，默认禁用）
    if config.get('clip_optimize_enable', False):
        try:
            from clip_feature import clip_feature_optimization
            steps.append(('🆕 CLIP 特征优化', lambda p: clip_feature_optimization(p, {
                'enable_clip': True,
            })))
        except ImportError as e:
            logger.warning(f"⚠️ CLIP 特征模块未导入：{e}")
    
    for step_name, step_func in steps:
        try:
            new_path = step_func(current_path)
            if new_path != current_path:
                # 删除旧文件
                if os.path.exists(current_path) and current_path != input_path:
                    os.remove(current_path)
                current_path = new_path
                logger.info(f"✅ {step_name} 完成")
        except Exception as e:
            logger.warning(f"⚠️ {step_name} 失败：{e}")
    
    # 移动到最终输出路径
    if output_path is None:
        output_path = input_path.rsplit('.', 1)[0] + '_enhanced.jpg'
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 移动文件
    shutil.move(current_path, output_path)
    
    # 清理临时目录
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except:
        pass
    
    logger.info(f"✨ 真实性增强完成（12 步终极优化）：{output_path}")
    return output_path


def batch_enhance(input_dir: str, output_dir: str, config: Optional[dict] = None):
    """
    批量增强图片
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        config: 配置字典
    """
    from pathlib import Path
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 查找所有图片
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    image_files = [f for f in input_path.iterdir() if f.suffix.lower() in image_extensions]
    
    logger.info(f"📁 找到 {len(image_files)} 张图片")
    
    for image_file in image_files:
        output_file = output_path / f"{image_file.stem}_enhanced.jpg"
        try:
            enhance_realism(str(image_file), str(output_file), config)
            logger.info(f"✅ {image_file.name} → {output_file.name}")
        except Exception as e:
            logger.error(f"❌ {image_file.name} 处理失败：{e}")
    
    logger.info(f"✨ 批量处理完成")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AI 图片真实性增强工具')
    parser.add_argument('input', help='输入图片路径或目录')
    parser.add_argument('-o', '--output', help='输出图片路径或目录')
    parser.add_argument('--jpeg-quality', type=int, default=90, help='JPEG 质量 (85-95)')
    parser.add_argument('--blur-radius', type=float, default=0.3, help='模糊半径 (0.3-0.5)')
    parser.add_argument('--sharp-strength', type=float, default=0.15, help='锐化强度 (0.1-0.2)')
    parser.add_argument('--grain-iso', type=int, default=300, help='胶片颗粒 ISO (200-400)')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 判断是单文件还是目录
    input_path = Path(args.input)
    
    if input_path.is_dir():
        # 批量处理
        if args.output is None:
            args.output = str(input_path / 'enhanced')
        batch_enhance(args.input, args.output, {
            'jpeg_quality': args.jpeg_quality,
            'blur_radius': args.blur_radius,
            'sharp_strength': args.sharp_strength,
            'grain_iso': args.grain_iso,
        })
    else:
        # 单文件处理
        enhance_realism(args.input, args.output, {
            'jpeg_quality': args.jpeg_quality,
            'blur_radius': args.blur_radius,
            'sharp_strength': args.sharp_strength,
            'grain_iso': args.grain_iso,
        })
