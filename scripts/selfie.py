#!/usr/bin/env python3
"""selfie.py - 自拍生成模块 (Wan2.6-image 图生图)"""

import dashscope
import os
import sys
import json
import base64
import logging
import re
import time
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_IMAGE_SIZE = "2K"
PROMPT_EXTEND = True
MAX_INPUT_LENGTH = 500

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception): pass
class FileNotFoundError(Exception): pass


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    if not text: return ""
    if len(text) > max_length:
        logger.warning(f"输入过长，已截断至 {max_length}")
        text = text[:max_length]
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f`$(){};|&!\\]', '', text)


def validate_channel(channel: Optional[str]) -> Optional[str]:
    if not channel: return None
    valid_channels = {'feishu', 'telegram', 'discord', 'whatsapp'}
    return channel.lower() if channel.lower() in valid_channels else None


def validate_config() -> str:
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if not api_key:
        raise ConfigurationError("API Key 未设置")
    return api_key


def validate_character_image() -> Path:
    script_dir = Path(__file__).resolve().parent
    character_path = script_dir.parent / 'assets/default-character.png'
    if not character_path.exists():
        raise FileNotFoundError(f"头像文件不存在：{character_path}")
    return character_path


def get_image_base64(image_path: Path) -> str:
    with open(image_path, 'rb') as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"


def build_prompt(context: str) -> Tuple[str, str]:
    context_lower = context.lower()
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"在对镜自拍，{context}，全身照，镜子反射，自然光线，真实感，高清"
    return "direct", f"{context}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"


def call_image_api(image_path: Path, prompt: str, api_key: str) -> str:
    dashscope.api_key = api_key
    input_image_base64 = get_image_base64(image_path)
    logger.info(f"🖼️ 使用本地头像")
    
    import requests
    payload = {
        'model': 'wan2.6-image',
        'input': {'messages': [{'role': 'user', 'content': [{'image': input_image_base64}, {'text': prompt}]}]},
        'parameters': {'prompt_extend': PROMPT_EXTEND, 'watermark': False, 'n': 1, 'enable_interleave': False, 'size': DEFAULT_IMAGE_SIZE}
    }
    
    response = requests.post(
        'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload, timeout=120
    )
    
    result_json = response.json()
    if response.status_code == 200 and result_json.get('output'):
        output = result_json['output']
        if 'choices' in output and len(output['choices']) > 0:
            return output['choices'][0]['message']['content'][0]['image']
    raise Exception(f"API 错误：{result_json}")


def send_to_channel(image_url: str, caption: str, channel: str) -> bool:
    try:
        logger.info(f"📤 发送到：{channel}")
        import requests, subprocess
        temp_file = f'/tmp/openclaw/selfie_{int(time.time())}.jpg'
        os.makedirs('/tmp/openclaw', exist_ok=True)
        
        with open(temp_file, 'wb') as f:
            f.write(requests.get(image_url).content)
        
        result = subprocess.run(['openclaw', 'message', 'send', '--action', 'send', '--channel', channel, '--message', caption, '--media', temp_file], capture_output=True, text=True)
        os.remove(temp_file)
        
        if result.returncode == 0:
            logger.info("✓ 图片发送成功")
            return True
        logger.error(f"发送失败：{result.stderr}")
        return False
    except Exception as e:
        logger.error(f"发送异常：{e}")
        return False


def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None) -> Optional[str]:
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")
        
        image_path = validate_character_image()
        logger.info("✅ 头像文件验证通过")
        
        context = sanitize_input(context)
        if not context:
            logger.error("无效的场景描述")
            return None
        
        channel = validate_channel(channel)
        mode, prompt = build_prompt(context)
        logger.info(f"📸 模式：{mode}")
        
        image_url = call_image_api(image_path, prompt, api_key)
        
        if channel and image_url:
            send_to_channel(image_url, caption, channel)
        
        return image_url
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 selfie.py <场景描述> [频道] [配文]")
        sys.exit(1)
    
    context = sys.argv[1]
    channel = sys.argv[2] if len(sys.argv) > 2 else None
    caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
    
    result = generate_selfie(context, caption, channel)
    sys.exit(0 if result else 1)
