#!/usr/bin/env python3.11
"""selfie_v2.py - 角色替换生成模块 (双图输入)

支持模式:
1. 角色替换：参考图 + 小柔头像 → 小柔在参考图场景下 (保持服装/姿势/场景不变)

核心功能:
- 双图输入：第一张参考图 (场景/服装/姿势),第二张小柔头像 (人物身份)
- 提示词强调：保持参考图一切内容，只替换人物为小柔
- 使用 wan2.7-image 模型
"""

import os
import sys
import json
import base64
import logging
import re
import time
import threading
import shutil
import subprocess
import requests
import uuid
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse

# 导入统一配置
from config import config, ConfigurationError, ALLOWED_IMAGE_DIRS

# ========== 常量定义 ==========
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
MAX_IMAGE_SIZE_MB = 10
MAX_PROMPT_LENGTH = 6000
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))
IMAGE_DOWNLOAD_TIMEOUT = int(os.environ.get('XIAOROU_IMAGE_DOWNLOAD_TIMEOUT', '60'))

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# 飞书 token 缓存
_feishu_token: Optional[str] = None
_feishu_token_time: float = 0
_feishu_token_lock = threading.Lock()


def _has_path_traversal(file_path: str) -> bool:
    """检查路径是否包含遍历攻击 (..)"""
    return ".." in str(file_path)


def _is_absolute_path(file_path: str) -> bool:
    """检查路径是否为绝对路径"""
    return os.path.isabs(file_path)


def is_safe_path(base_dir: Path, file_path: str) -> bool:
    """检查文件路径是否在允许的目录内"""
    try:
        if _has_path_traversal(file_path):
            logger.warning(f"检测到路径遍历尝试:{file_path}")
            return False
        if not _is_absolute_path(file_path):
            logger.warning(f"拒绝相对路径:{file_path}")
            return False
        base_dir = base_dir.resolve()
        resolved = Path(file_path).resolve(strict=True)
        try:
            resolved.relative_to(base_dir)
            return True
        except ValueError:
            return False
    except (OSError, ValueError) as e:
        logger.debug(f"路径安全检查失败:{e}")
        return False


def validate_image_file(file_path: str) -> bool:
    """验证图片文件类型"""
    magic_bytes = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'RIFF....WEBP': 'webp',
    }
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
        if header[:3] == b'\xff\xd8\xff':
            return True
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True
        return False
    except Exception as e:
        logger.debug(f"图片魔数检查失败:{e}")
        return False


def sanitize_input(text: str, max_length: int = 500) -> str:
    """净化用户输入"""
    if not text:
        return ""
    if len(text) > max_length:
        text = text[:max_length]
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'[`$(){};|&<>[\]*?\\@]', '', text)
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)
    return text


def validate_channel(channel: Optional[str]) -> Optional[str]:
    if not channel:
        return None
    valid_channels = {'feishu', 'telegram', 'discord', 'whatsapp'}
    return channel.lower() if channel.lower() in valid_channels else None


def validate_config() -> str:
    """验证并加载 API Key"""
    return config.get_api_key()


def validate_character_image() -> Path:
    """验证小柔头像文件是否存在"""
    script_dir = Path(__file__).resolve().parent
    character_path = script_dir.parent / 'assets/default-character.png'
    if not character_path.exists():
        raise FileNotFoundError(f"头像文件不存在:{character_path}")
    return character_path


def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64 格式"""
    file_size = image_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"图片文件为空:{image_path}")
    if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"图片文件过大:{file_size / 1024 / 1024:.2f}MB(限制 10MB)")
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/png'
    with open(image_path, 'rb') as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"


def build_role_swap_prompt(reference_description: str = "") -> str:
    """
    构建角色替换 prompt - 双图输入精简版
    
    Args:
        reference_description: 参考图的额外描述 (可选)
    
    Returns:
        完整的角色替换 prompt
    """
    # 核心指令：角色替换（双图输入 - AI 直接看参考图）
    instruction = """【角色替换 - 双图输入】
输入图 1：参考图（AI 直接看）| 输入图 2：小柔头像（人物身份）
目标：保持参考图一切内容（服装/姿势/场景/光影），只换人脸为小柔

【核心要求 - 权重 5.0】
- **(无水印：5.0)** - 禁止任何水印/文字/logo/签名
- **(100% 小柔脸：5.0)** - 完全使用图 2 的脸/发型/肤色
- **(脸部角度匹配：5.0)** - 正脸/侧脸/低头/抬头与参考图一致
- **(光源一致性：5.0)** - 光影/阴影/高光与参考图统一
- **(头身比例：5.0)** - 头身比 1:7-1:8，头部大小正常

【禁止】
- 使用参考图的脸/发型/肤色
- 继承参考图的水印/文字
- 头部过大过小/比例失调
- AI 感/塑料感/畸形
"""

    # 质量标签
    quality_tags = "8K, (无水印：5.0), (头身比 1:7-1:8:5.0)"

    # 反向提示词
    negative_tags = "(worst quality, low quality:1.4), (watermark,text,logo:5.0), (big head:5.0), (deformed:1.3)"

    full_prompt = f"""{instruction}
{quality_tags}
{negative_tags}
Keep EVERYTHING from reference (outfit/pose/scene/lighting/face angle), ONLY swap face to 小柔 (图 2). Match yaw/pitch/roll, blend lighting (shadows/highlights). NO watermark. Head-body ratio 1:7-1:8."""

    return full_prompt


def generate_role_swap_image(reference_image_path: Path, character_image_path: Path, prompt: str, api_key: str, max_retries: int = 2) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7-image 进行角色替换生成 (双图输入)

    Args:
        reference_image_path: 参考图路径 (场景/服装/姿势)
        character_image_path: 小柔头像路径 (人物身份)
        prompt: 提示词
        api_key: API Key
        max_retries: 最大重试次数

    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    model_name = 'wan2.7-image'
    
    for attempt in range(max_retries + 1):
        try:
            reference_base64 = get_image_base64(reference_image_path)
            character_base64 = get_image_base64(character_image_path)
            logger.info(f"🖼️ 双图输入模式：参考图 + 小柔头像 (尝试 {attempt + 1}/{max_retries + 1})")

            # Prompt 长度校验
            if len(prompt) > MAX_PROMPT_LENGTH:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {MAX_PROMPT_LENGTH}),已截断")
                prompt = prompt[:MAX_PROMPT_LENGTH]

            # 双图输入：参考图 + 小柔头像
            content = [
                {'image': reference_base64},      # 参考图 (场景/服装/姿势)
                {'image': character_base64},      # 小柔头像 (人物身份)
                {'text': prompt}                   # 角色替换提示词
            ]
            logger.info(f"🖼️ 双图输入：图 1(参考) + 图 2(小柔) + 文字 prompt")

            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': content}]},
                'parameters': {
                    'prompt_extend': False,
                    'watermark': False,
                    'n': 1,
                    'enable_interleave': False,
                    'size': '1536*2048',  # 3:4 竖版高清
                }
            }

            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
                },
                json=payload,
                timeout=API_TIMEOUT
            )

            result_json = response.json()
            if response.status_code == 200 and result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    logger.info(f"✅ {model_name} 生成成功")
                    return (model_name, image_url)

            logger.error(f"❌ {model_name} API 错误:{result_json}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)

        except json.JSONDecodeError as e:
            logger.error(f"❌ {model_name} JSON 解析失败:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except requests.RequestException as e:
            logger.error(f"❌ {model_name} 请求异常:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception as e:
            logger.error(f"❌ {model_name} 错误:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)


def get_feishu_credentials() -> Tuple[Optional[str], Optional[str]]:
    """获取飞书 API 凭证"""
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                openclaw_config = json.load(f)
            app_id = openclaw_config.get('channels', {}).get('feishu', {}).get('appId', '')
            app_secret = openclaw_config.get('channels', {}).get('feishu', {}).get('appSecret', '')
            if app_id and app_secret:
                return app_id, app_secret
        except Exception as e:
            logger.debug(f"读取飞书配置失败:{e}")
    return None, None


def get_feishu_access_token() -> Optional[str]:
    """获取飞书 access_token"""
    global _feishu_token, _feishu_token_time
    if _feishu_token and (time.time() - _feishu_token_time) < 7200:
        return _feishu_token
    with _feishu_token_lock:
        if _feishu_token and (time.time() - _feishu_token_time) < 7200:
            return _feishu_token
        app_id, app_secret = get_feishu_credentials()
        if not app_id or not app_secret:
            return None
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        try:
            token_response = requests.post(
                token_url,
                headers={"Content-Type": "application/json"},
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=30
            )
            token_data = token_response.json()
            access_token = token_data.get('tenant_access_token', '')
            if access_token:
                _feishu_token = access_token
                _feishu_token_time = time.time()
                return access_token
        except Exception as e:
            logger.warning(f"获取飞书 access_token 失败:{e}")
    return None


def upload_feishu_image(image_file: str) -> Optional[str]:
    """上传图片到飞书"""
    access_token = get_feishu_access_token()
    if not access_token:
        return None
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
        logger.info(f"✅ 飞书图片上传成功:{image_key}")
        return image_key
    return None


def send_feishu_image_message(image_key: str, caption: str, receive_id: str, receive_id_type: Optional[str] = None) -> bool:
    """发送飞书原生图片消息"""
    access_token = get_feishu_access_token()
    if not access_token:
        return False
    if receive_id_type is None:
        if receive_id.startswith('ou_'):
            receive_id_type = 'open_id'
        elif receive_id.startswith('on_'):
            receive_id_type = 'union_id'
        else:
            return False
    message_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    content = json.dumps({"image_key": image_key, "text": caption})
    message_data = {"receive_id": receive_id, "msg_type": "image", "content": content}
    response = requests.post(
        message_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=message_data,
        timeout=60
    )
    result = response.json()
    return result.get('code') == 0


def _download_image(image_url: str, temp_file: str) -> bool:
    """下载图片到临时文件"""
    try:
        response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()
        final_url = response.url
        allowed_domains = ['dashscope.aliyuncs.com', 'aliyuncs.com', 'volces.com']
        parsed = urlparse(final_url)
        hostname = parsed.hostname or ''
        is_allowed = any(hostname == domain or hostname.endswith('.' + domain) for domain in allowed_domains)
        if not is_allowed:
            return False
        if len(response.history) > 5:
            return False
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            return False
        max_download_size = MAX_IMAGE_SIZE_BYTES
        downloaded = 0
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    if downloaded > max_download_size:
                        return False
                    f.write(chunk)
        return os.path.getsize(temp_file) > 0
    except Exception as e:
        logger.error(f"下载图片失败:{e}")
        return False


def send_to_channel(image_url: str, caption: str, channel: str, model_name: str, target: Optional[str] = None) -> bool:
    """发送图片到频道"""
    try:
        logger.info(f"📤 发送到:{channel}")
        temp_dir = config.get_temp_dir()
        temp_file = f'{temp_dir}/selfie_{uuid.uuid4().hex[:8]}.jpg'
        os.makedirs(str(temp_dir), mode=0o700, exist_ok=True)
        if not _download_image(image_url, temp_file):
            return False
        # 飞书使用原生图片消息
        if channel == 'feishu':
            send_target = target or os.environ.get('AEVIA_TARGET', '')
            if not send_target:
                send_target = config.get_feishu_target()
            if not send_target:
                logger.error("未配置飞书目标用户")
                return False
            image_key = upload_feishu_image(temp_file)
            if image_key:
                if send_feishu_image_message(image_key, caption, send_target):
                    logger.info("✓ 飞书原生图片发送成功")
                    return True
        else:
            send_target = target or os.environ.get('AEVIA_TARGET', '')
            cmd_args = ['openclaw', 'message', 'send', '--channel', channel, '--target', send_target, '--message', caption, '--media', temp_file]
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        return False
    except Exception as e:
        logger.error(f"发送异常:{e}")
        return False


def generate_role_swap(reference_image_path: str, caption: str = "这是角色替换生成的~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    角色替换模式：参考图 + 小柔头像 → 小柔在参考图场景下

    Args:
        reference_image_path: 参考图路径
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标

    Returns:
        是否成功
    """
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")

        # 验证参考图
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            logger.error(f"参考图不存在:{reference_image_path}")
            return False
        logger.info("✅ 参考图验证通过")

        # 加载小柔头像
        character_path = validate_character_image()
        logger.info("✅ 头像文件验证通过")

        channel = validate_channel(channel)

        # 构建角色替换 prompt
        prompt = build_role_swap_prompt()
        logger.info(f"📸 角色替换模式")

        # 双图输入生成
        logger.info("🚀 wan2.7-image 生成中 (双图输入：参考图 + 小柔头像)...")
        model_name, image_url = generate_role_swap_image(ref_path, character_path, prompt, api_key)

        if not image_url:
            logger.error("❌ 生成失败")
            return False

        # 发送生成的图片
        if channel:
            effective_target = target or os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, model_name, effective_target):
                logger.info("✅ 发送成功")
                return True
            else:
                logger.error("❌ 发送失败")
                return False
        return True

    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误:{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误:{e}")
        return False


if __name__ == "__main__":
    import fcntl

    LOCK_FILE = str(config.get_temp_dir() / "selfie_task.lock")
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    if len(sys.argv) < 2:
        print("用法:")
        print("  角色替换：python3 selfie_v2.py --role-swap <参考图路径> [频道] [配文] [target]")
        sys.exit(1)

    if sys.argv[1] == '--role-swap' and len(sys.argv) >= 3:
        reference_image = sys.argv[2]
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在:{reference_image}")
            sys.exit(1)
        channel = sys.argv[3] if len(sys.argv) > 3 else None
        caption = sys.argv[4] if len(sys.argv) > 4 else "这是角色替换生成的~"
        target = sys.argv[5] if len(sys.argv) > 5 else None
        success = generate_role_swap(reference_image, caption, channel, target)
        sys.exit(0 if success else 1)
    else:
        print("用法:")
        print("  角色替换：python3 selfie_v2.py --role-swap <参考图路径> [频道] [配文] [target]")
        sys.exit(1)
