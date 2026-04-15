#!/usr/bin/env python3
"""
frequency_optimize.py - 频域优化模块

基于《AI 图片识别技术深度研究报告》实现频域反检测技术。
频域分析是最有效的 AI 图片检测方法 (92% 准确率)，本模块通过频域优化来对抗检测。

功能：
1. 频谱平滑 - 消除 AI 生成的周期性伪影
2. 1/f 噪声注入 - 模拟自然场景的频谱特性
3. 频域增强 - 综合频域优化

技术原理：
- AI 生成图像在频域有独特的频谱模式（周期性伪影）
- 真实图像的频谱遵循 1/f 分布（自然场景统计特性）
- 通过平滑频谱和注入 1/f 噪声，让 AI 图更接近真实图像的频谱特性

使用方式：
    from frequency_optimize import frequency_domain_enhance
    frequency_domain_enhance('input.jpg', config)
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


def fft2(image_array: np.ndarray) -> np.ndarray:
    """2D 快速傅里叶变换"""
    from scipy import fftpack
    return fftpack.fft2(image_array)


def ifft2(spectrum: np.ndarray) -> np.ndarray:
    """2D 逆快速傅里叶变换"""
    from scipy import fftpack
    return np.real(fftpack.ifft2(spectrum))


def fftshift(spectrum: np.ndarray) -> np.ndarray:
    """频谱中心化"""
    from scipy import fftpack
    return fftpack.fftshift(spectrum)


def ifftshift(spectrum: np.ndarray) -> np.ndarray:
    """频谱反中心化"""
    from scipy import fftpack
    return fftpack.ifftshift(spectrum)


def spectral_smoothing(image_path: str, sigma: float = 0.5) -> str:
    """
    频谱平滑 - 消除 AI 生成的周期性伪影
    
    技术原理：
    - AI 生成图像在频域常有网格状/周期性伪影
    - 通过高斯滤波器平滑频谱，消除这些伪影
    - 保持低频信息（图像主要内容），平滑高频（伪影区域）
    
    Args:
        image_path: 输入图片路径
        sigma: 高斯滤波器 sigma 值 (0.3-0.8 推荐)
               越大平滑越强，但可能损失细节
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        from scipy.ndimage import gaussian_filter
        
        # 读取图片
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)
        
        # FFT 变换
        spectrum = fft2(img_array)
        spectrum_shifted = fftshift(spectrum)
        
        # 计算频谱幅度
        magnitude = np.abs(spectrum_shifted)
        phase = np.angle(spectrum_shifted)
        
        # 高斯平滑频谱幅度
        smoothed_magnitude = gaussian_filter(magnitude, sigma=sigma)
        
        # 重建频谱
        smoothed_spectrum = smoothed_magnitude * np.exp(1j * phase)
        smoothed_spectrum_unshifted = ifftshift(smoothed_spectrum)
        
        # 逆 FFT
        result = ifft2(smoothed_spectrum_unshifted)
        
        # 裁剪到有效范围
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_spectral.jpg'
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 频谱平滑完成 (sigma={sigma})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 频谱平滑失败：{e}")
        return image_path


def add_natural_spectrum(image_path: str, strength: float = 0.15) -> str:
    """
    添加 1/f 自然频谱噪声
    
    技术原理：
    - 真实自然图像的频谱遵循 1/f 分布（pink noise 特性）
    - AI 生成图像的频谱分布与真实图像有显著差异
    - 注入符合 1/f 分布的噪声，让 AI 图频谱更接近真实图像
    
    Args:
        image_path: 输入图片路径
        strength: 噪声强度 (0.1-0.3 推荐)
                  越大越接近真实频谱，但可能引入可见噪声
    
    Returns:
        输出图片路径
    """
    try:
        from PIL import Image
        
        # 读取图片
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape
        
        # FFT 变换
        spectrum = fft2(img_array)
        spectrum_shifted = fftshift(spectrum)
        
        # 生成 1/f 噪声频谱
        # 1/f 噪声：功率谱密度与频率成反比
        u = np.fft.fftfreq(h)
        v = np.fft.fftfreq(w)
        U, V = np.meshgrid(v, u)
        freq = np.sqrt(U**2 + V**2)
        
        # 避免除零
        freq[freq == 0] = 1
        
        # 1/f 频谱
        natural_spectrum = 1.0 / np.sqrt(freq + 1e-10)
        
        # 归一化
        natural_spectrum = natural_spectrum / np.max(natural_spectrum)
        
        # 生成随机相位
        random_phase = np.exp(1j * 2 * np.pi * np.random.random((h, w)))
        
        # 合成 1/f 噪声
        noise_spectrum = natural_spectrum * random_phase * strength * np.max(np.abs(spectrum_shifted))
        
        # 添加到原频谱
        combined_spectrum = spectrum_shifted + noise_spectrum
        
        # 逆 FFT
        combined_spectrum_unshifted = ifftshift(combined_spectrum)
        result = ifft2(combined_spectrum_unshifted)
        
        # 裁剪到有效范围
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        # 保存结果
        output_path = image_path.rsplit('.', 1)[0] + '_natural_spec.jpg'
        result_img = Image.fromarray(result)
        result_img.save(output_path, 'JPEG', quality=95)
        
        logger.info(f"✅ 1/f 自然频谱噪声添加完成 (strength={strength})")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 1/f 自然频谱噪声添加失败：{e}")
        return image_path


def frequency_domain_enhance(image_path: str, config: Optional[Dict] = None) -> str:
    """
    频域增强主函数
    
    完整流程：
    1. 频谱平滑（消除周期性伪影）
    2. 1/f 噪声注入（模拟自然频谱）
    3. 融合输出
    
    Args:
        image_path: 输入图片路径
        config: 配置字典
            - spectral_sigma: 频谱平滑 sigma (默认 0.5)
            - natural_spectrum_strength: 1/f 噪声强度 (默认 0.15)
            - enable_spectral_smoothing: 是否启用频谱平滑 (默认 True)
            - enable_natural_spectrum: 是否启用 1/f 噪声 (默认 True)
    
    Returns:
        输出图片路径
    """
    # 默认配置
    default_config = {
        'spectral_sigma': 0.5,
        'natural_spectrum_strength': 0.15,
        'enable_spectral_smoothing': True,
        'enable_natural_spectrum': True,
    }
    
    # 合并配置（支持环境变量覆盖）
    config = {**default_config, **(config or {})}
    config['spectral_sigma'] = float(os.environ.get('XIAOROU_SPECTRAL_SIGMA', config['spectral_sigma']))
    config['natural_spectrum_strength'] = float(os.environ.get('XIAOROU_NATURAL_SPECTRUM_STRENGTH', config['natural_spectrum_strength']))
    
    # 检查依赖
    if not check_dependencies():
        logger.warning("⚠️ 依赖缺失，跳过频域优化")
        return image_path
    
    try:
        from PIL import Image
        
        current_path = image_path
        
        # 步骤 1: 频谱平滑
        if config.get('enable_spectral_smoothing', True):
            current_path = spectral_smoothing(current_path, sigma=config['spectral_sigma'])
        
        # 步骤 2: 1/f 自然频谱噪声
        if config.get('enable_natural_spectrum', True):
            current_path = add_natural_spectrum(current_path, strength=config['natural_spectrum_strength'])
        
        logger.info(f"✅ 频域增强完成：{current_path}")
        return current_path
        
    except Exception as e:
        logger.error(f"❌ 频域增强失败：{e}")
        return image_path


def analyze_frequency_characteristics(image_path: str) -> Dict:
    """
    分析图像的频域特征（用于调试和验证）
    
    Args:
        image_path: 输入图片路径
    
    Returns:
        频域特征字典
    """
    try:
        from PIL import Image
        
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)
        
        # FFT 变换
        spectrum = fft2(img_array)
        spectrum_shifted = fftshift(spectrum)
        magnitude = np.abs(spectrum_shifted)
        
        # 计算径向分布
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2
        u = np.fft.fftfreq(h)
        v = np.fft.fftfreq(w)
        U, V = np.meshgrid(v, u)
        freq_radius = np.sqrt(U**2 + V**2)
        
        # 分频段计算能量
        low_freq_mask = freq_radius < 0.1
        mid_freq_mask = (freq_radius >= 0.1) & (freq_radius < 0.3)
        high_freq_mask = freq_radius >= 0.3
        
        low_energy = np.sum(magnitude[low_freq_mask])
        mid_energy = np.sum(magnitude[mid_freq_mask])
        high_energy = np.sum(magnitude[high_freq_mask])
        total_energy = low_energy + mid_energy + high_energy
        
        # 计算 1/f 拟合度
        # 真实图像的频谱应该接近 1/f 分布
        freq_nonzero = freq_radius[freq_radius > 0]
        mag_nonzero = magnitude[freq_radius > 0]
        
        # 对数空间的线性拟合
        log_freq = np.log(freq_nonzero + 1e-10)
        log_mag = np.log(mag_nonzero + 1e-10)
        
        # 简单拟合
        slope, _ = np.polyfit(log_freq, log_mag, 1)
        
        return {
            'low_freq_ratio': low_energy / total_energy,
            'mid_freq_ratio': mid_energy / total_energy,
            'high_freq_ratio': high_energy / total_energy,
            'spectral_slope': slope,  # 真实图像应该接近 -1 (1/f)
            'total_energy': total_energy,
        }
        
    except Exception as e:
        logger.error(f"❌ 频域分析失败：{e}")
        return {}


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python3 frequency_optimize.py <图片路径> [输出路径]")
        print("示例：python3 frequency_optimize.py input.jpg output.jpg")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 分析原始特征
    print("\n📊 原始图像频域特征:")
    features = analyze_frequency_characteristics(input_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
    
    # 频域增强
    print("\n🚀 开始频域优化...")
    result_path = frequency_domain_enhance(input_path)
    print(f"✅ 输出：{result_path}")
    
    # 分析优化后特征
    print("\n📊 优化后图像频域特征:")
    features = analyze_frequency_characteristics(result_path)
    for k, v in features.items():
        print(f"  {k}: {v:.4f}")
