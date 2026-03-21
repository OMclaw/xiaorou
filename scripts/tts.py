#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts.py - 文字转语音模块

使用 Google TTS 服务生成语音（免费，无需 API Key）

使用示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
"""

import argparse
import logging
import os
import sys
import subprocess
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
# 支持的音色（中文）
AVAILABLE_VOICES = [
    "zh-CN-XiaoxiaoNeural",    # 温柔女声（推荐）
    "zh-CN-YunxiNeural",       # 男声
    "zh-CN-YunjianNeural",     # 男声
    "zh-CN-XiaoyiNeural",      # 女声
    "zh-CN-XiaochenNeural",    # 女声
    "zh-CN-XiaohanNeural",     # 女声
]

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"  # 默认音色（温柔女声）

# 获取脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_SH_PATH = os.path.join(SCRIPT_DIR, 'tts.sh')


# ============================================
# TTS 生成（使用 tts.sh）
# ============================================
def text_to_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE
) -> Tuple[bool, str]:
    """
    使用 tts.sh 生成语音
    
    Args:
        text: 待转换的文本
        output_path: 输出文件路径
        voice: 音色名称
        
    Returns:
        (成功标志，消息/错误信息)
    """
    if not text or not text.strip():
        return False, "文本不能为空"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 调用 tts.sh 脚本
        cmd = ['bash', TTS_SH_PATH, text.strip(), output_path, voice]
        
        logger.info(f"生成语音：voice={voice}, text_length={len(text)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"语音生成成功：{output_path} ({file_size} bytes)")
            return True, output_path
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else result.stdout.decode('utf-8', errors='ignore')
            logger.error(f"TTS 失败：{error_msg}")
            return False, f"TTS 失败：{error_msg}"
            
    except subprocess.TimeoutExpired:
        logger.error("TTS 生成超时")
        return False, "TTS 生成超时"
    except Exception as e:
        logger.exception(f"未知错误：{e}")
        return False, f"未知错误：{e}"


def list_available_voices() -> list:
    """获取可用音色列表"""
    return AVAILABLE_VOICES.copy()


# ============================================
# 命令行接口
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description='文字转语音 (Google TTS)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python tts.py "你好，我是小柔" /tmp/voice.mp3
  python tts.py --text "早上好" --output /tmp/morning.mp3
  python tts.py --text "你好" --voice zh-CN-XiaoxiaoNeural
  python tts.py --list-voices  # 列出可用音色
        '''
    )
    
    parser.add_argument('text', nargs='?', help='待转换的文本')
    parser.add_argument('output', nargs='?', help='输出文件路径')
    parser.add_argument('--text', '-t', dest='text_arg', help='待转换的文本')
    parser.add_argument('--output', '-o', dest='output_arg', help='输出文件路径')
    parser.add_argument('--voice', '-v', default=DEFAULT_VOICE, 
                       help=f'音色 (默认：{DEFAULT_VOICE})')
    parser.add_argument('--list-voices', action='store_true',
                       help='列出可用音色')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_voices:
        print("可用音色:")
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
        voice=args.voice
    )
    
    if success:
        logger.info("✓ 转换完成")
        return 0
    else:
        logger.error(f"✗ 转换失败：{message}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
