#!/usr/bin/env python3
"""selfie.py - 自拍生成模块 (Wan2.6-image 图生图)

支持两种模式：
1. 普通模式：根据文字描述生成
2. 参考图模式：分析参考图后生成模仿图
"""

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
PROMPT_EXTEND = False  # 关闭自动扩展，避免过度美化导致假
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
    """验证并加载 API Key，支持环境变量和 OpenClaw 配置文件"""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
        logger.info("✓ 从环境变量加载 API Key")
        return api_key
    
    # 从 OpenClaw 配置文件读取
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 尝试两种配置路径
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            if not api_key:
                api_key = config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
            if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
                logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise ConfigurationError("API Key 未设置，请配置环境变量或 ~/.openclaw/openclaw.json")


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
    """构建网红风格图片生成 prompt - 增强真实感版本"""
    context_lower = context.lower()
    
    # 网红风格基础元素 - 减少 AI 感，增加真实感
    influencer_style = "网红风格，精致妆容，时尚穿搭，专业摄影"
    
    # 真实感增强标签 - 关键！
    realistic_tags = "真实摄影，自然皮肤纹理，毛孔细节，真实光影，胶片质感，生活照风格，无 AI 感，无塑料感"
    
    # 质量标签
    quality_tags = "8K 超高清，电影级布光，细节丰富，色彩自然"
    
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"{influencer_style}，{context}，全身照，对镜拍摄，网红打卡场景，自然光线，{realistic_tags}，{quality_tags}"
    
    # 默认网红风格 prompt - 强调真实感
    return "direct", f"{influencer_style}，{context}，眼神直视镜头，自然微笑，真实五官，时尚造型，网红打卡背景，{realistic_tags}，{quality_tags}"


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


def get_feishu_credentials():
    """获取飞书 API 凭证"""
    import json
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 尝试新配置格式（直接 channels.feishu.appId）
            app_id = config.get('channels', {}).get('feishu', {}).get('appId', '')
            app_secret = config.get('channels', {}).get('feishu', {}).get('appSecret', '')
            
            # 兼容旧配置格式（accounts 数组）
            if not app_id or not app_secret:
                default_account = config.get('channels', {}).get('feishu', {}).get('defaultAccount', 'main')
                accounts = config.get('channels', {}).get('feishu', {}).get('accounts', {})
                app_id = accounts.get(default_account, {}).get('appId', '')
                app_secret = accounts.get(default_account, {}).get('appSecret', '')
            
            if app_id and app_secret:
                return app_id, app_secret
        except Exception as e:
            logger.debug(f"读取飞书配置失败：{e}")
    
    # 尝试环境变量
    app_id = os.environ.get('FEISHU_APP_ID', '')
    app_secret = os.environ.get('FEISHU_APP_SECRET', '')
    if app_id and app_secret:
        return app_id, app_secret
    
    return None, None


def upload_feishu_image(image_file: str) -> Optional[str]:
    """上传图片到飞书，返回 image_key"""
    import requests
    
    app_id, app_secret = get_feishu_credentials()
    if not app_id or not app_secret:
        logger.warning("未配置飞书凭证，无法使用原生图片格式")
        return None
    
    # 1. 获取 access_token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    token_response = requests.post(
        token_url,
        headers={"Content-Type": "application/json"},
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30
    )
    token_data = token_response.json()
    access_token = token_data.get('tenant_access_token', '')
    
    if not access_token:
        logger.warning("获取飞书 access_token 失败")
        return None
    
    # 2. 上传图片文件
    # 飞书要求：image_type=message 表示用于发送消息的图片
    upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
    with open(image_file, 'rb') as f:
        files = {'image': (os.path.basename(image_file), f, 'image/jpeg')}
        data = {'image_type': 'message'}
        upload_response = requests.post(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}"},
            files=files,
            data=data,
            timeout=60
        )
    
    upload_data = upload_response.json()
    if upload_data.get('code') == 0:
        image_key = upload_data.get('data', {}).get('image_key', '')
        logger.info(f"✅ 飞书图片上传成功：{image_key}")
        return image_key
    
    logger.warning(f"飞书图片上传失败：{upload_data}")
    return None


def send_feishu_image_message(image_key: str, caption: str, receive_id: str, receive_id_type: str = "open_id") -> bool:
    """发送飞书原生图片消息"""
    import requests
    
    app_id, app_secret = get_feishu_credentials()
    if not app_id or not app_secret:
        return False
    
    # 获取 access_token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    token_response = requests.post(
        token_url,
        headers={"Content-Type": "application/json"},
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30
    )
    token_data = token_response.json()
    access_token = token_data.get('tenant_access_token', '')
    
    if not access_token:
        return False
    
    # 发送图片消息
    message_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    content = json.dumps({"image_key": image_key, "text": caption})
    message_data = {
        "receive_id": receive_id,
        "msg_type": "image",
        "content": content
    }
    
    response = requests.post(
        message_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=message_data,
        timeout=60
    )
    
    result = response.json()
    if result.get('code') == 0:
        logger.info("✅ 飞书原生图片消息发送成功")
        return True
    
    logger.error(f"飞书图片消息发送失败：{result}")
    return False


def send_to_channel(image_url: str, caption: str, channel: str, target: Optional[str] = None) -> bool:
    """发送图片到频道，飞书使用原生图片格式，其他平台使用文件"""
    try:
        logger.info(f"📤 发送到：{channel} (target: {target or 'auto'})")
        import requests, subprocess
        
        timestamp = int(time.time())
        temp_file = f'/tmp/openclaw/selfie_{timestamp}.jpg'
        os.makedirs('/tmp/openclaw', exist_ok=True)
        
        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        # 验证文件是否有效
        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return False
        
        # 飞书平台：尝试使用原生图片格式
        if channel == "feishu":
            send_target = target or os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')
            receive_id = send_target.replace('user:', '') if send_target.startswith('user:') else send_target
            
            # 上传到飞书并发送原生图片消息
            image_key = upload_feishu_image(temp_file)
            if image_key:
                success = send_feishu_image_message(image_key, caption, receive_id, "open_id")
                os.remove(temp_file)
                return success
        
        # 其他平台或飞书降级方案：使用 openclaw message send
        send_target = target or os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')
        
        cmd_args = [
            'openclaw', 'message', 'send',
            '--channel', channel,
            '--target', send_target,
            '--message', caption,
            '--media', temp_file
        ]
        
        result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
        
        # 清理临时文件
        try:
            os.remove(temp_file)
        except:
            logger.warning(f"清理临时文件失败：{temp_file}")
        
        if result.returncode == 0:
            logger.info("✓ 图片发送成功")
            return True
        
        logger.error(f"发送失败：{result.stderr}")
        return False
        
    except requests.RequestException as e:
        logger.error(f"下载图片异常：{e}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("发送超时")
        return False
    except Exception as e:
        logger.error(f"发送异常：{e}")
        return False


def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None, target: Optional[str] = None) -> Optional[str]:
    """普通模式：根据文字描述生成图片"""
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
            if not target:
                target = os.environ.get('AEVIA_TARGET')
            send_to_channel(image_url, caption, channel, target)
        
        return image_url
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


def generate_from_reference(reference_image_path: str, caption: str = "这是模仿参考图生成的～", channel: Optional[str] = None, target: Optional[str] = None) -> Optional[str]:
    """
    参考图模式：分析参考图后生成模仿图
    
    Args:
        reference_image_path: 参考图路径
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标
    
    Returns:
        生成的图片 URL，失败返回 None
    """
    try:
        # 1. 分析参考图
        logger.info("🔍 正在分析参考图...")
        script_dir = Path(__file__).resolve().parent
        analyzer_path = script_dir / 'image_analyzer.py'
        
        if not analyzer_path.exists():
            logger.error(f"图片分析模块不存在：{analyzer_path}")
            return None
        
        import subprocess
        result = subprocess.run(
            ['python3.11', str(analyzer_path), reference_image_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"图片分析失败：{result.stderr}")
            return None
        
        reference_prompt = result.stdout.strip()
        logger.info(f"✅ 参考图分析完成：{reference_prompt[:100]}...")
        
        # 2. 使用小柔头像 + 参考图 prompt 生成
        return generate_selfie(reference_prompt, caption, channel, target)
        
    except subprocess.TimeoutExpired:
        logger.error("图片分析超时")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 selfie.py <场景描述 | --reference 参考图路径> [频道] [配文] [target]")
        sys.exit(1)
    
    # 检测是否为参考图模式
    if sys.argv[1] == '--reference' and len(sys.argv) >= 3:
        # 参考图模式
        reference_image = sys.argv[2]
        channel = sys.argv[3] if len(sys.argv) > 3 else None
        caption = sys.argv[4] if len(sys.argv) > 4 else "这是模仿参考图生成的～"
        target = sys.argv[5] if len(sys.argv) > 5 else None
        
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在：{reference_image}")
            sys.exit(1)
        
        result = generate_from_reference(reference_image, caption, channel, target)
    else:
        # 普通模式
        context = sys.argv[1]
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
        target = sys.argv[4] if len(sys.argv) > 4 else None
        
        result = generate_selfie(context, caption, channel, target)
    
    sys.exit(0 if result else 1)
