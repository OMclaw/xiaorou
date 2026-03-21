#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts.py - 文字转语音模块 (阿里云 CosyVoice 官方 SDK)

功能:
  - 使用阿里云 CosyVoice 模型将文字转换为语音
  - 支持自定义音色（温柔女声）
  - 输出格式：MP3
  - 完善的错误处理和日志记录
  - 自动从 OpenClaw 配置加载 API Key

使用示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
  python tts.py --voice longxiaoyu --text "你好" --output test.mp3

依赖:
  - dashscope (阿里云官方 SDK)
  - Python 3.9+
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# 导入 dashscope SDK
try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer
except ImportError:
    print("❌ 缺少依赖：dashscope", file=sys.stderr)
    print("   请运行：pip3 install dashscope", file=sys.stderr)
    sys.exit(1)

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
# 支持的音色列表（CosyVoice v3）
AVAILABLE_VOICES = [
    "longanyang",      # 温暖女声（推荐，默认）
    "longxiaochun",    # 青春女声
    "longcheng",       # 成熟男声
    "longxiaoyu",      # 甜美女声
    "longxiaoxia",     # 知性女声
    "longya",          # 温柔女声
    "longwan",         # 温柔女声
]

DEFAULT_VOICE = "longyingxiao_v3"  # 默认音色（温柔女声）
DEFAULT_MODEL = "cosyvoice-v3-flash"  # 默认模型（快速版）

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
    
    return text


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


def load_api_key() -> str:
    """
    从环境变量或配置文件加载 API Key
    
    Returns:
        API Key 字符串
        
    Raises:
        TTSError: 无法加载有效的 API Key
    """
    # 优先使用环境变量
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    
    if validate_api_key(api_key):
        return api_key
    
    # 尝试从 OpenClaw 配置文件加载
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 尝试路径：models.providers.dashscope.apiKey
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            
            if validate_api_key(api_key):
                logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise TTSError("无法加载 API Key，请设置 DASHSCOPE_API_KEY 环境变量或检查 OpenClaw 配置")


def text_to_speech(
    text: str,
    output_path: str,
    api_key: Optional[str] = None,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
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
        try:
            api_key = load_api_key()
        except TTSError as e:
            logger.error(str(e))
            return False, str(e)
    
    # 设置 SDK 的 API Key
    dashscope.api_key = api_key
    
    # 验证音色
    if voice not in AVAILABLE_VOICES:
        logger.warning(f"音色 '{voice}' 不在推荐列表中，但仍会尝试使用")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 执行请求（带重试）
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"正在生成语音 (尝试 {attempt}/{retries})...")
            logger.debug(f"请求参数：model={model}, voice={voice}, text_length={len(text)}")
            
            # 创建 SpeechSynthesizer
            synthesizer = SpeechSynthesizer(model=model, voice=voice)
            
            # 调用 API 生成语音
            audio = synthesizer.call(text)
            
            # 保存到文件
            with open(output_path, 'wb') as f:
                f.write(audio)
            
            # 输出统计信息
            file_size = os.path.getsize(output_path)
            request_id = synthesizer.get_last_request_id()
            delay = synthesizer.get_first_package_delay()
            
            logger.info(f"✓ 语音生成成功")
            logger.info(f"  文件：{output_path} ({file_size} bytes)")
            logger.info(f"  Request ID: {request_id}")
            logger.info(f"  首包延迟：{delay}ms")
            
            return True, output_path
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"API 错误：{error_msg}")
            
            if attempt < retries:
                wait_time = RETRY_DELAY * attempt
                logger.warning(f"{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                return False, f"API 错误：{error_msg}"
    
    return False, "未知错误"


# ============================================
# 命令行接口
# ============================================
def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='阿里云 CosyVoice 文字转语音',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
  python tts.py --voice longxiaochun --text "你好" --output test.mp3
        """
    )
    
    parser.add_argument('text', nargs='?', help='待转换的文本')
    parser.add_argument('output', nargs='?', help='输出文件路径')
    parser.add_argument('--text', '-t', dest='text_arg', help='待转换的文本（替代位置参数）')
    parser.add_argument('--output', '-o', dest='output_arg', help='输出文件路径（替代位置参数）')
    parser.add_argument('--voice', '-v', default=DEFAULT_VOICE, 
                        help=f'音色名称 (默认：{DEFAULT_VOICE})')
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL,
                        help=f'模型名称 (默认：{DEFAULT_MODEL})')
    parser.add_argument('--list-voices', action='store_true',
                        help='列出可用的音色')
    parser.add_argument('--verbose', action='store_true',
                        help='显示详细日志')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 列出可用音色
    if args.list_voices:
        print("可用的音色:")
        for voice in AVAILABLE_VOICES:
            print(f"  - {voice}")
        sys.exit(0)
    
    # 获取文本和输出路径
    text = args.text_arg or args.text
    output = args.output_arg or args.output
    
    if not text:
        parser.error("请提供待转换的文本")
    
    if not output:
        parser.error("请提供输出文件路径")
    
    # 执行转换
    success, message = text_to_speech(
        text=text,
        output_path=output,
        voice=args.voice,
        model=args.model
    )
    
    if success:
        print(f"✅ 语音生成成功：{output}")
        sys.exit(0)
    else:
        print(f"❌ 语音生成失败：{message}")
        sys.exit(1)


if __name__ == '__main__':
    # 使用 Python 3.9+
    if sys.version_info < (3, 9):
        print(f"❌ 需要 Python 3.9+，当前版本：{sys.version}", file=sys.stderr)
        sys.exit(1)
    
    main()
