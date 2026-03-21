#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts.py - 文字转语音模块 (CosyVoice)

功能:
  - 使用阿里云 CosyVoice 模型将文字转换为语音
  - 支持自定义音色（温柔女声）
  - 输出格式：MP3
  - 完善的错误处理和日志记录

使用示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3

依赖:
  - requests (已在 requirements.txt 中)
  - 无需额外安装 cosyvoice SDK（使用 HTTP API 调用）
"""

import argparse
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

# ============================================
# 日志配置
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('cosyvoice-tts')

# ============================================
# 常量定义
# ============================================
# CosyVoice API 端点（阿里云百炼兼容模式）
COSYVOICE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/speech"

# 支持的音色列表（温柔女声优先）
AVAILABLE_VOICES = [
    "longxiaochun",    # 温柔女声（推荐）
    "longxiaoman",     # 活泼女声
    "longxiaoxia",     # 知性女声
    "longxiaoyu",      # 甜美女声
    "longxiaoyan",     # 成熟女声
]

DEFAULT_VOICE = "longxiaochun"  # 默认音色
DEFAULT_MODEL = "cosyvoice-v3.5-plus"  # 默认模型
DEFAULT_FORMAT = "mp3"  # 默认输出格式
DEFAULT_SAMPLE_RATE = 24000  # 默认采样率

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒

# 输入验证配置
MAX_TEXT_LENGTH = 500  # 最大文本长度


# ============================================
# 错误处理
# ============================================
class TTSError(Exception):
    """TTS 相关错误基类"""
    pass


class APIError(TTSError):
    """API 调用错误"""
    pass


class ValidationError(TTSError):
    """输入验证错误"""
    pass


# ============================================
# 核心功能
# ============================================
def validate_text(text: str) -> str:
    """
    验证和清理输入文本
    
    Args:
        text: 待转换的文本
        
    Returns:
        清理后的文本
        
    Raises:
        ValidationError: 文本无效或过长
    """
    if not text or not text.strip():
        raise ValidationError("输入文本不能为空")
    
    # 清理空白字符
    text = text.strip()
    
    # 长度检查
    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(f"文本长度 {len(text)} 超过限制，已截断为 {MAX_TEXT_LENGTH}")
        text = text[:MAX_TEXT_LENGTH]
    
    # 移除控制字符（保留中文、英文、数字和常见标点）
    cleaned = ''.join(
        char for char in text 
        if ord(char) >= 32 or char in '\n\t'
    )
    
    return cleaned


def validate_api_key(api_key: str) -> bool:
    """
    验证 API Key 格式
    
    Args:
        api_key: API Key 字符串
        
    Returns:
        是否有效
    """
    if not api_key:
        return False
    
    # 阿里云 API Key 格式：sk- 开头，至少 20 个字符
    import re
    return bool(re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key))


def text_to_speech(
    text: str,
    output_path: str,
    api_key: Optional[str] = None,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    audio_format: str = DEFAULT_FORMAT,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    speed: float = 1.0,
    retries: int = MAX_RETRIES
) -> Tuple[bool, str]:
    """
    将文字转换为语音并保存为文件
    
    Args:
        text: 待转换的文本
        output_path: 输出文件路径
        api_key: 阿里云 API Key（如不提供则从环境变量读取）
        voice: 音色名称
        model: 模型名称
        audio_format: 输出格式（mp3/wav/pcm）
        sample_rate: 采样率
        speed: 语速（0.5-2.0）
        retries: 最大重试次数
        
    Returns:
        (成功标志，消息/错误信息)
    """
    # 验证输入
    try:
        text = validate_text(text)
    except ValidationError as e:
        logger.error(f"输入验证失败：{e}")
        return False, str(e)
    
    # 加载 API Key
    if not api_key:
        api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    
    if not validate_api_key(api_key):
        error_msg = "API Key 无效，请设置 DASHSCOPE_API_KEY 环境变量"
        logger.error(error_msg)
        return False, error_msg
    
    # 验证音色
    if voice not in AVAILABLE_VOICES:
        logger.warning(f"音色 '{voice}' 不在推荐列表中，但仍会尝试使用")
    
    # 验证语速
    if not (0.5 <= speed <= 2.0):
        logger.warning(f"语速 {speed} 超出范围，已调整为 1.0")
        speed = 1.0
    
    # 准备请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "input": {
            "text": text
        },
        "parameters": {
            "voice": voice,
            "response_format": audio_format,
            "sample_rate": sample_rate,
            "speed": speed
        }
    }
    
    # 创建临时文件（安全存储）
    temp_file = None
    try:
        # 执行请求（带重试）
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"正在生成语音 (尝试 {attempt}/{retries})...")
                logger.debug(f"请求参数：model={model}, voice={voice}, text_length={len(text)}")
                
                response = requests.post(
                    COSYVOICE_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=30  # 30 秒超时
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    # 确保输出目录存在
                    output_dir = os.path.dirname(output_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    
                    # 写入临时文件
                    temp_fd, temp_path = tempfile.mkstemp(suffix=f'.{audio_format}')
                    temp_file = temp_path
                    
                    try:
                        with os.fdopen(temp_fd, 'wb') as f:
                            f.write(response.content)
                        
                        # 移动到目标位置
                        os.replace(temp_path, output_path)
                        temp_file = None  # 标记已成功移动
                        
                        file_size = os.path.getsize(output_path)
                        logger.info(f"语音生成成功：{output_path} ({file_size} bytes)")
                        return True, output_path
                    
                    except Exception as e:
                        # 清理临时文件
                        if temp_file and os.path.exists(temp_file):
                            os.unlink(temp_file)
                        raise
                    
                elif response.status_code in [429, 500, 502, 503]:
                    # 可重试的错误
                    if attempt < retries:
                        wait_time = RETRY_DELAY * attempt
                        logger.warning(f"API 请求失败 ({response.status_code})，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise APIError(f"API 请求失败 ({response.status_code})，已重试 {retries} 次")
                
                else:
                    # 不可重试的错误
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', response.text)
                    except:
                        error_msg = response.text
                    
                    raise APIError(f"API 错误 ({response.status_code}): {error_msg}")
                
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    wait_time = RETRY_DELAY * attempt
                    logger.warning(f"网络错误：{e}，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise APIError(f"网络请求失败：{e}")
        
        # 所有重试都失败
        raise APIError(f"API 请求失败，已重试 {retries} 次")
        
    except (APIError, ValidationError) as e:
        logger.error(str(e))
        return False, str(e)
    except Exception as e:
        logger.exception(f"未知错误：{e}")
        return False, f"未知错误：{e}"
    finally:
        # 清理临时文件（如果还存在）
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.debug(f"已清理临时文件：{temp_file}")
            except:
                pass


def list_available_voices() -> list:
    """
    获取可用音色列表
    
    Returns:
        音色列表
    """
    return AVAILABLE_VOICES.copy()


# ============================================
# 命令行接口
# ============================================
def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='文字转语音 (CosyVoice)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
  python tts.py --text "你好" --voice longxiaoxia --speed 1.2
        '''
    )
    
    parser.add_argument('text', nargs='?', help='待转换的文本')
    parser.add_argument('output', nargs='?', help='输出文件路径')
    parser.add_argument('--text', '-t', dest='text_arg', help='待转换的文本（替代位置参数）')
    parser.add_argument('--output', '-o', dest='output_arg', help='输出文件路径（替代位置参数）')
    parser.add_argument('--voice', '-v', default=DEFAULT_VOICE, 
                       help=f'音色 (默认：{DEFAULT_VOICE})')
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL,
                       help=f'模型 (默认：{DEFAULT_MODEL})')
    parser.add_argument('--format', '-f', default=DEFAULT_FORMAT,
                       choices=['mp3', 'wav', 'pcm'],
                       help=f'输出格式 (默认：{DEFAULT_FORMAT})')
    parser.add_argument('--speed', '-s', type=float, default=1.0,
                       help='语速 0.5-2.0 (默认：1.0)')
    parser.add_argument('--list-voices', action='store_true',
                       help='列出可用音色')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 列出音色
    if args.list_voices:
        print("可用音色:")
        for voice in AVAILABLE_VOICES:
            marker = " (默认)" if voice == DEFAULT_VOICE else ""
            print(f"  - {voice}{marker}")
        return 0
    
    # 获取文本和输出路径
    text = args.text or args.text_arg
    output = args.output or args.output_arg
    
    if not text or not output:
        parser.print_help()
        return 1
    
    # 执行转换
    success, message = text_to_speech(
        text=text,
        output_path=output,
        voice=args.voice,
        model=args.model,
        audio_format=args.format,
        speed=args.speed
    )
    
    if success:
        logger.info("✓ 转换完成")
        return 0
    else:
        logger.error("✗ 转换失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
