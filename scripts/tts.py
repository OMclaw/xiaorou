#!/usr/bin/env python3
"""tts.py - 文字转语音 (阿里云 CosyVoice 官方 SDK)"""

import argparse
import json
import logging
import os
import sys
import time
import re
from pathlib import Path
from typing import Optional, Tuple

try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
except ImportError:
    print("❌ 缺少依赖：dashscope\n   请运行：pip3 install dashscope", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger('cosyvoice-tts')

AVAILABLE_VOICES = ["longanyang", "longxiaochun", "longcheng", "longxiaoyu", "longxiaoxia", "longya", "longwan"]
DEFAULT_VOICE = "longyingxiao_v3"
DEFAULT_MODEL = "cosyvoice-v3-flash"
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_TEXT_LENGTH = 500


class TTSError(Exception): pass
class APIError(TTSError): pass
class ValidationError(TTSError): pass


def validate_text(text: str) -> str:
    if not text or not text.strip():
        raise ValidationError("输入文本不能为空")
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(f"文本过长，已截断为 {MAX_TEXT_LENGTH}")
        text = text[:MAX_TEXT_LENGTH]
    return text


def load_api_key() -> str:
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
        return api_key
    
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            if api_key:
                logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise TTSError("无法加载 API Key，请设置 DASHSCOPE_API_KEY 环境变量")


def get_audio_duration(audio_path: str) -> Optional[int]:
    """获取音频时长（毫秒），用于飞书语音消息"""
    try:
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            duration_sec = float(result.stdout.strip())
            return int(duration_sec * 1000)
    except Exception as e:
        logger.debug(f"获取音频时长失败：{e}")
    
    return None


def validate_opus_file(file_path: str) -> bool:
    """验证 OPUS 文件是否符合飞书要求（OPUS 编码，24/48kHz，单声道）"""
    try:
        import subprocess
        import json
        
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'stream=codec_name,sample_rate,channels',
            '-of', 'json',
            file_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return False
        
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        if not streams:
            return False
        
        stream = streams[0]
        codec = stream.get('codec_name', '')
        sample_rate = int(stream.get('sample_rate', 0))
        channels = int(stream.get('channels', 0))
        
        # 飞书要求：OPUS 编码，24kHz 或 48kHz，单声道
        if codec != 'opus':
            logger.warning(f"OPUS 验证：编码格式不符：{codec}")
            return False
        if sample_rate not in [24000, 48000]:
            logger.warning(f"OPUS 验证：采样率不符：{sample_rate}")
            return False
        if channels != 1:
            logger.warning(f"OPUS 验证：声道数不符：{channels}")
            return False
        
        logger.info("✓ OPUS 格式验证通过")
        return True
    except Exception as e:
        logger.debug(f"OPUS 验证异常：{e}")
        return True  # 验证失败不阻止发送


def text_to_speech(text: str, output_path: str, voice: str = DEFAULT_VOICE, model: str = DEFAULT_MODEL, retries: int = MAX_RETRIES) -> Tuple[bool, str]:
    try:
        text = validate_text(text)
    except ValidationError as e:
        logger.error(f"输入验证失败：{e}")
        return False, str(e)
    
    try:
        api_key = load_api_key()
    except TTSError as e:
        logger.error(str(e))
        return False, str(e)
    
    dashscope.api_key = api_key
    
    if voice not in AVAILABLE_VOICES:
        logger.warning(f"音色 '{voice}' 不在推荐列表中")
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"正在生成语音 (尝试 {attempt}/{retries})...")
            
            if output_path.endswith('.opus'):
                audio_format = AudioFormat.OGG_OPUS_24KHZ_MONO_32KBPS
            elif output_path.endswith('.wav'):
                audio_format = AudioFormat.WAV_24000HZ_MONO_16BIT
            else:
                audio_format = AudioFormat.MP3_24000HZ_MONO_256KBPS
            
            synthesizer = SpeechSynthesizer(model=model, voice=voice, format=audio_format)
            audio = synthesizer.call(text)
            
            with open(output_path, 'wb') as f:
                f.write(audio)
            
            file_size = os.path.getsize(output_path)
            logger.info(f"✓ 语音生成成功 ({file_size} bytes)")
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


def main():
    parser = argparse.ArgumentParser(description='阿里云 CosyVoice 文字转语音')
    parser.add_argument('text', nargs='?', help='待转换的文本')
    parser.add_argument('output', nargs='?', help='输出文件路径')
    parser.add_argument('--text', '-t', dest='text_arg', help='待转换的文本')
    parser.add_argument('--output', '-o', dest='output_arg', help='输出文件路径')
    parser.add_argument('--voice', '-v', default=DEFAULT_VOICE, help=f'音色名称 (默认：{DEFAULT_VOICE})')
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL, help=f'模型名称')
    parser.add_argument('--list-voices', action='store_true', help='列出可用音色')
    parser.add_argument('--verbose', action='store_true', help='显示详细日志')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_voices:
        print("可用的音色:")
        for voice in AVAILABLE_VOICES:
            print(f"  - {voice}")
        sys.exit(0)
    
    text = args.text_arg or args.text
    output = args.output_arg or args.output
    
    if not text:
        parser.error("请提供待转换的文本")
    if not output:
        parser.error("请提供输出文件路径")
    
    success, message = text_to_speech(text=text, output_path=output, voice=args.voice, model=args.model)
    
    if success:
        # 获取音频时长并输出（供 shell 脚本使用）
        duration = get_audio_duration(output)
        if duration:
            print(f"✅ 语音生成成功：{output} (时长：{duration}ms)")
            # 写入时长文件供 shell 脚本读取
            duration_file = output + '.duration'
            try:
                with open(duration_file, 'w') as f:
                    f.write(str(duration))
                logger.debug(f"时长已写入：{duration_file}")
            except Exception as e:
                logger.debug(f"写入时长文件失败：{e}")
        else:
            print(f"✅ 语音生成成功：{output}")
        
        # 如果是 OPUS 格式，进行验证
        if output.endswith('.opus'):
            validate_opus_file(output)
        
        sys.exit(0)
    else:
        print(f"❌ 语音生成失败：{message}")
        sys.exit(1)


if __name__ == '__main__':
    if sys.version_info < (3, 9):
        print(f"❌ 需要 Python 3.9+，当前版本：{sys.version}", file=sys.stderr)
        sys.exit(1)
    main()
