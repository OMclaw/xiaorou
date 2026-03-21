#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts.py - 文字转语音模块

使用阿里云 CosyVoice (DashScope) 服务生成语音

使用示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
"""

import argparse
import logging
import os
import sys
from typing import Tuple

# ============================================
# 日志配置
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tts')

# ============================================
# 常量定义
# ============================================
# 支持的音色（CosyVoice）
AVAILABLE_VOICES = [
    "longqiang_v3",        # 成熟男声（推荐）
    "longxiaochun_v2",     # 温柔女声
    "longxiaoman_v2",      # 活泼女声
    "longxiaoxia_v2",      # 知性女声
    "longxiaoyu_v2",       # 甜美女声
    "longxiaoyan_v2",      # 成熟女声
    "longanyang",          # 阳光男声
]

DEFAULT_VOICE = "longqiang_v3"  # 默认音色（成熟男声）

# 获取脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================
# API Key 管理
# ============================================
def get_api_key() -> str:
    """
    获取 DashScope API Key
    
    优先级:
    1. 环境变量 DASHSCOPE_API_KEY
    2. ~/.openclaw/openclaw.json 配置
    """
    # 优先使用环境变量
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key:
        return api_key
    
    # 尝试从 OpenClaw 配置读取
    config_path = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 查找 dashscope API Key
            for ext in config.get('extensions', {}).values():
                if isinstance(ext, dict):
                    env = ext.get('env', {})
                    if 'DASHSCOPE_API_KEY' in env:
                        return env['DASHSCOPE_API_KEY']
        except Exception as e:
            logger.debug(f"读取 OpenClaw 配置失败：{e}")
    
    return ''


def validate_api_key(api_key: str) -> bool:
    """验证 API Key 格式"""
    if not api_key:
        return False
    # DashScope API Key 格式：sk-开头，长度至少 20 字符
    return api_key.startswith('sk-') and len(api_key) >= 20


# ============================================
# 文本验证
# ============================================
def validate_text(text: str) -> str:
    """验证并清理文本"""
    if not text:
        raise ValueError("文本不能为空")
    return text.strip()


# ============================================
# TTS 生成（使用 CosyVoice API）
# ============================================
def text_to_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    model: str = "cosyvoice-v3-flash",
    retries: int = 2
) -> Tuple[bool, str]:
    """
    使用 CosyVoice API 生成语音
    
    Args:
        text: 待转换的文本
        output_path: 输出文件路径
        voice: 音色名称
        model: 模型名称
        retries: 重试次数
        
    Returns:
        (成功标志，消息/错误信息)
    """
    try:
        text = validate_text(text)
    except ValueError as e:
        return False, str(e)
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 获取 API Key
    api_key = get_api_key()
    if not validate_api_key(api_key):
        return False, "无效的 API Key，请设置 DASHSCOPE_API_KEY 环境变量"
    
    # 尝试导入 dashscope
    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
    except ImportError:
        return False, "未安装 dashscope 库，请运行：pip install dashscope"
    
    # 设置 API Key
    dashscope.api_key = api_key
    
    # 重试逻辑
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"生成语音 (尝试 {attempt}/{retries}): model={model}, voice={voice}, text_length={len(text)}")
            
            # 创建合成器
            synthesizer = SpeechSynthesizer(model=model, voice=voice)
            
            # 合成语音
            audio = synthesizer.call(text)
            
            # 获取性能指标
            request_id = synthesizer.get_last_request_id()
            first_pkg_delay = synthesizer.get_first_package_delay()
            logger.info(f"Request ID: {request_id}, 首包延迟：{first_pkg_delay:.2f}ms")
            
            # 保存到文件
            with open(output_path, 'wb') as f:
                f.write(audio)
            
            file_size = os.path.getsize(output_path)
            logger.info(f"语音生成成功：{output_path} ({file_size} bytes)")
            return True, output_path
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"尝试 {attempt} 失败：{error_msg}")
            
            if attempt == retries:
                logger.error(f"TTS 生成最终失败：{error_msg}")
                return False, f"TTS 生成失败：{error_msg}"
    
    return False, "未知错误"


def list_available_voices() -> list:
    """获取可用音色列表"""
    return AVAILABLE_VOICES.copy()


# ============================================
# 命令行接口
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description='文字转语音 (CosyVoice)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
  python tts.py --text "你好" --voice longqiang_v3
  python tts.py --list-voices  # 列出可用音色
        '''
    )
    
    parser.add_argument('text', nargs='?', help='待转换的文本')
    parser.add_argument('output', nargs='?', help='输出文件路径')
    parser.add_argument('--text', '-t', dest='text_arg', help='待转换的文本')
    parser.add_argument('--output', '-o', dest='output_arg', help='输出文件路径')
    parser.add_argument('--voice', '-v', default=DEFAULT_VOICE, 
                       help=f'音色 (默认：{DEFAULT_VOICE})')
    parser.add_argument('--model', '-m', default='cosyvoice-v3-flash',
                       help='模型 (默认：cosyvoice-v3-flash)')
    parser.add_argument('--list-voices', action='store_true',
                       help='列出可用音色')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_voices:
        print("可用音色 (CosyVoice):")
        for voice in AVAILABLE_VOICES:
            marker = " (默认)" if voice == DEFAULT_VOICE else ""
            print(f"  - {voice}{marker}")
        return 0
    
    text = args.text or args.text_arg
    output = args.output or args.output_arg
    
    if not text or not output:
        parser.print_help()
        return 1
    
    success, message = text_to_speech(
        text=text,
        output_path=output,
        voice=args.voice,
        model=args.model
    )
    
    if success:
        logger.info("✓ 转换完成")
        return 0
    else:
        logger.error(f"✗ 转换失败：{message}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
