#!/usr/bin/env python3.11
"""selfie_v2.py - 角色替换生成模块 (双图输入)

支持模式:
1. 角色替换:参考图 + 图二 → 图二人物在参考图场景下 (保持服装/姿势/场景不变)

核心功能:
- 双图输入:第一张参考图 (场景/服装/姿势),第二张图二 (人物身份)
- 提示词强调:保持参考图一切内容,只替换人物为图二人物
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
    """验证图 2文件是否存在"""
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
    构建角色替换 prompt - v6.2.0 完整版

    Args:
        reference_description: 参考图的额外描述 (可选)

    Returns:
        完整的角色替换 prompt
    """
    # 完整 prompt - 格式化排版
    full_prompt = f"""【核心指令 - 整体重新生成】
**这不是简单的脸部替换,而是基于参考图重新生成一张完整的照片**
图 1(参考图):提供场景/服装/姿势/光影/构图参考 -> **整体画面重新渲染**
图二(人物正脸):提供正面五官特征、脸型、发型 -> **人物身份参考**
输出 = **一张全新的、自然融合的照片**,基于图二的人物特征,人物完全融入场景,无拼贴感/无贴上去的感觉

【必须保持 - 图 1 内容】
- 场景背景、服装穿搭、姿势动作
- 光源方向/强度/色温、阴影/高光位置
- 构图视角、景深效果、整体色调
- 环境光遮蔽、接触阴影、衣物反射光
- 原图人脸的角度/朝向/俯仰/侧转 -> 替换脸必须完全对齐

【必须保持 - 图二内容】
- 图二(人物正脸):提供正面五官特征、脸型、发型
- **100% 保留图二人物的五官特征**,确保人物身份一致性
- **肤色智能适配**:保留图二五官特征,但肤色亮度根据图 1 身体肤色自适应调整
- 五官比例关系不变形,仅做角度适配

【必须忽略 - 图 1 内容】
- 原图人脸五官(完全替换,仅保留角度参考)
- 原图发型/发色/肤色
- 所有水印/文字/logo(彻底去除,绝对禁止保留任何形式的水印,包括右下角/角落/边缘水印)

【光影与肤色融合 - 整体统一】
- **整张照片统一光源**:人物和场景在同一光源下,无独立光照
- 面部光影严格匹配图 1 光源方向,高光/阴影位置与身体一致
- 面部色温与身体色温完全统一,暖光场景面部偏暖,冷光场景面部偏冷
- 面部受环境光影响:图 1 有蓝色环境反射则面部带蓝调,有暖色反射则面部带暖调
- **肤色自适应匹配**:根据图 1 身体肤色智能调整面部肤色亮度,身体偏暗则面部同步偏暗,身体偏白则面部同步偏白
- **禁止脸部过白**:面部肤色不得明显亮于身体肤色,避免脸部惨白/死白/过曝/突兀
- **自然肤色过渡**:脸部/颈部/身体肤色无缝过渡,无分界线/色差/色块
- 面部对比度/饱和度与身体一致,不突兀不跳脱

【人脸角度对齐】
- 替换脸的角度/朝向必须与图 1 原人脸完全一致
- 正脸保持正脸,侧脸保持侧脸,俯仰角度完全对齐
- 视线方向与图 1 一致,眼睛看向同一方向
- 面部透视变形与图 1 镜头角度匹配,近大远小关系正确

【头部大小比例】
- **人物头/脸大小必须与参考图原人物的头/脸大小保持一致**
- 头部尺寸、脸部比例、头身比与参考图完全匹配
- 禁止头部过大或过小,保持与参考图相同的视觉比例
- 脸部宽度/高度与参考图原人脸比例一致

【面部光影肤色匹配】
- **图二脸部的光源方向必须与参考图原人物脸部的光源方向完全一致**
- **图二脸部的肤色亮度必须与参考图原人物脸部的肤色亮度完全一致**
- 面部高光/阴影位置与参考图原人脸完全匹配
- 面部色温与参考图原人脸完全匹配(暖光/冷光/自然光)
- 面部受光强度与参考图原人脸一致,禁止过亮或过暗
- 面部肤色饱和度与参考图原人脸一致

【整体融合 - 关键要求】
- **重新生成整张照片**:不是拼贴/合成/换脸,而是完整的新照片
- **人物完全融入场景**:人物是这个场景中自然存在的人物,无违和感
- **统一光影**:人物和场景在同一光源下,光影方向/强度/色温一致
- **统一色彩**:人物色彩与场景色彩协调,无独立调色
- **统一质感**:人物皮肤质感与照片整体质感一致,无突兀
- **禁止拼贴感**:无边缘痕迹/无分界线/无合成感/无贴上去的感觉

【比例协调】
- 脸部大小与身体比例协调,头身比一比八到一比九
- 下巴与颈部自然衔接,无断层/错位/比例失调
- 发际线过渡自然,鬓角与侧脸衔接流畅
- 精致小脸效果,五官分布符合人体解剖结构

【质量标准 - 整体统一】
- **整体画面重新生成**:不是拼贴/合成,而是一张完整的新照片
- **人物与场景统一**:人物完全融入场景,无违和感/无拼贴感
- **光影统一**:人物光影与场景光影完全一致,同一光源
- **色彩统一**:人物色彩与场景色彩协调,同一色调
- 边缘融合自然:下巴颈部衔接、发际线/鬓角过渡
- 皮肤真实质感:保留毛孔/微瑕/肤质纹理,皮肤半透明泛红效果

【参考图描述】{reference_description if reference_description else "标准人像场景,自然光线,清晰画质"}

【基础风格】网红审美风格,精致妆容,时尚穿搭,柔和滤镜

【真实感】
- 八十五毫米人像镜头虚化,微颗粒噪点,电影级色彩分级
- 柔和光照,体积光,轮廓光,照片级真实感

【质量标签】8K 超高清，绝对无水印，最高画质，杰作，画面纯净

【反向提示词】
权重 10.0:水印、文字、logo、平台水印、角落水印、右下角水印、边缘水印、透明水印、半透明水印、底部水印、顶部水印、签名、署名、网站地址、URL、@符号、社交媒体标识、抖音水印、快手水印、微博水印、小红书水印、B 站水印、YouTube 水印、TikTok 水印、Instagram 水印、Facebook 水印、任何形式的水印、任何文字标记、任何 logo 标识
权重 5.0:面部角度与原图不一致、面部与身体光影不一致、面部与身体色温不匹配、面部与身体肤色断层、头身比例失调、**头部过大/过小**、**脸部比例与原图不一致**、**面部光影与原图不一致**、**面部肤色亮度与原图不一致**、塑料皮肤、蜡质感、过度磨皮、娃娃脸、视线方向错误、**面部过白/惨白/死白**、**拼贴感/合成感/贴上去的感觉**
权重 4.0:对比度异常、锐度不足、景深错误、透视失真、CG 渲染感、卡通化、油光满面、死白肤色、面部过亮/过暗、面部色偏、面部扭曲变形、低画质、畸形、解剖错误、过曝、欠曝、色偏、**肤色突兀不协调**、**人物与场景分离感**"""
    return full_prompt


def generate_role_swap_image(reference_image_path: Path, character_image_path: Path, prompt: str, api_key: str, max_retries: int = 2) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7-image 进行角色替换生成 (双图输入)

    Args:
        reference_image_path: 参考图路径 (场景/服装/姿势)
        character_image_path: 图 2路径 (人物身份)
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
            logger.info(f"🖼️ 双图输入模式:参考图 + 图二 (尝试 {attempt + 1}/{max_retries + 1})")

            # Prompt 长度校验
            if len(prompt) > MAX_PROMPT_LENGTH:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {MAX_PROMPT_LENGTH}),已截断")
                prompt = prompt[:MAX_PROMPT_LENGTH]

            # 双图输入:参考图 (图 1) + 图二
            # 图 1=参考图 (提供场景),图二=人物正脸 (提供脸部)
            content = [
                {'image': reference_base64},      # 图 1: 参考图 (提供场景 - 要保留的场景)
                {'image': character_base64},      # 图二:人物正脸 (提供脸部 - 要替换的脸)
                {'text': prompt}                   # 角色替换提示词
            ]
            logger.info(f"🖼️ 双图输入:图 1(参考场景) + 图二 (人物脸部) + 文字 prompt")

            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': content}]},
                'parameters': {
                    'prompt_extend': False,
                    'watermark': False,
                    'n': 1,
                    'enable_interleave': False,
                    'size': '1536*2048',  # 3:4 竖版高清
                    # 移除 image_strength/denoising_strength - 这些是单图编辑参数,不适用于多图输入
                }
            }

            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'X-DashScope-DataInspection': '{\"input\":\"disable\",\"output\":\"disable\"}',
                    'X-DashScope-Log': 'disable',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
                    'X-DashScope-Log': 'disable',
                },
                json=payload,
                timeout=API_TIMEOUT
            )

            result_json = response.json()
            if response.status_code == 200 and result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    logger.info(f"{model_name} 生成成功")
                    return (model_name, image_url)

            logger.error(f"{model_name} API 错误:{result_json}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)

        except json.JSONDecodeError as e:
            logger.error(f"{model_name} JSON 解析失败:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except requests.RequestException as e:
            logger.error(f"{model_name} 请求异常:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception as e:
            logger.error(f"{model_name} 错误:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)


def generate_role_swap_image_three(reference_image_path: Path, character1_path: Path, character2_path: Path, prompt: str, api_key: str, max_retries: int = 2) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7-image 进行角色替换生成 (三图输入)

    Args:
        reference_image_path: 参考图路径 (场景/服装/姿势)
        character1_path: 图二 路径 (正脸参考)
        character2_path: 图三 路径 (多角度参考)
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
            character1_base64 = get_image_base64(character1_path)
            character2_base64 = get_image_base64(character2_path)
            logger.info(f"🖼️ 三图输入模式:参考图 + 图二 + 图三 (尝试 {attempt + 1}/{max_retries + 1})")

            # Prompt 长度校验
            if len(prompt) > MAX_PROMPT_LENGTH:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {MAX_PROMPT_LENGTH}),已截断")
                prompt = prompt[:MAX_PROMPT_LENGTH]

            # 三图输入:参考图 (图 1) + 图二(图 2) + 图三(图 3)
            # 图 1=参考图 (提供场景), 图 2=图 2 (提供正面五官), 图 3=图 3 (提供侧面/不同角度特征)
            content = [
                {'image': reference_base64},      # 图 1: 参考图 (提供场景)
                {'image': character1_base64},     # 图 2: 图二 (正脸参考)
                {'image': character2_base64},     # 图 3: 图三 (多角度参考)
                {'text': prompt}                   # 角色替换提示词
            ]
            logger.info(f"🖼️ 三图输入:图 1(参考场景) + 图 2(图 2) + 图 3(图 3) + 文字 prompt")

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
                    'X-DashScope-DataInspection': '{\"input\":\"disable\",\"output\":\"disable\"}',
                    'X-DashScope-Log': 'disable',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
                    'X-DashScope-Log': 'disable',
                },
                json=payload,
                timeout=API_TIMEOUT
            )

            result_json = response.json()
            if response.status_code == 200 and result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    logger.info(f"✅ {model_name} 生成成功 (三图输入)")
                    return (model_name, image_url)

            logger.error(f"❌ {model_name} API 错误:{result_json}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)

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
        logger.info(f"飞书图片上传成功:{image_key}")
        return image_key
    return None


def send_feishu_image_message(image_key: str, caption: str, receive_id: str, receive_id_type: Optional[str] = None) -> bool:
    """发送飞书原生图片消息"""
    from config import normalize_feishu_target
    
    access_token = get_feishu_access_token()
    if not access_token:
        return False
    
    # 标准化用户 ID（支持所有格式）
    try:
        if receive_id_type is None:
            receive_id, receive_id_type = normalize_feishu_target(receive_id)
    except ValueError as e:
        logger.error(f"用户 ID 格式错误：{e}")
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


def generate_edit_image(source_image_path: Path, edit_instruction: str, caption: str = "编辑完成~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    场景生图模式:纯文字描述 → 小柔在该场景下

    Args:
        source_image_path: 用户提供的原始图片路径(如"在海边看日落")
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标

    Returns:
        是否成功
    """
    try:
        api_key = validate_config()
        logger.info(f"API Key 已加载")

        # 验证原图
        if not source_image_path.exists():
            logger.error(f"原图不存在:{source_image_path}")
            return False
        logger.info("✅ 原图验证通过")

        channel = validate_channel(channel)

        # 构建图像编辑 prompt - 只保留用户原始指令
        prompt = edit_instruction
        logger.info(f"🎨 图像编辑模式:{edit_instruction}")

        # 单图输入生成(仅图 2 + 文字 prompt)
        logger.info("🚀 wan2.7-image 生成中 (单图输入:图 2 + 场景描述)...")
        model_name, image_url = generate_edit_image_with_instruction(source_image_path, prompt, api_key)

        if not image_url:
            logger.error("生成失败")
            return False

        # 发送生成的图片
        if channel:
            effective_target = target or os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, model_name, effective_target):
                logger.info("发送成功")
                return True
            else:
                logger.error("发送失败")
                return False
        else:
            logger.info(f"生成成功:{image_url}")
            return True

    except Exception as e:
        logger.error(f"图像编辑错误:{e}")
        return False


def generate_edit_image_with_instruction(source_image_path: Path, prompt: str, api_key: str, max_retries: int = 2) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7-image 进行图像编辑 (单图输入)

    Args:
        character_image_path: 图 2路径
        prompt: 编辑指令 prompt
        api_key: API Key
        max_retries: 最大重试次数

    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    model_name = 'wan2.7-image'

    for attempt in range(max_retries + 1):
        try:
            source_base64 = get_image_base64(source_image_path)
            logger.info(f"🖼️ 单图输入模式:图 2 + 文字 prompt (尝试 {attempt + 1}/{max_retries + 1})")

            # Prompt 长度校验
            if len(prompt) > MAX_PROMPT_LENGTH:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {MAX_PROMPT_LENGTH}),已截断")
                prompt = prompt[:MAX_PROMPT_LENGTH]

            # 单图输入:原图 + 用户指令(简单直接)
            content = [
                {'image': source_base64},      # 原图
                {'text': prompt}                 # 用户原始指令
            ]
            logger.info(f"🖼️ 单图输入:原图 + 用户指令")

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
                    'X-DashScope-DataInspection': '{\"input\":\"disable\",\"output\":\"disable\"}',
                    'X-DashScope-Log': 'disable',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
                    'X-DashScope-Log': 'disable',
                },
                json=payload,
                timeout=API_TIMEOUT
            )

            result_json = response.json()
            if response.status_code == 200 and result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    logger.info(f"{model_name} 生成成功")
                    return (model_name, image_url)

            logger.error(f"{model_name} API 错误:{result_json}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)

        except Exception as e:
            logger.error(f"{model_name} 错误:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)


def generate_role_swap(reference_image_path: str, caption: str = "这是角色替换生成的~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    角色替换模式:参考图 + 图 2 (双图或三图输入) → 小柔在参考图场景下

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

        # 加载图二(正脸参考)
        character_path = validate_character_image()
        logger.info("✅ 图二 验证通过(正脸参考)")

        # 双图模式 (参考图 + 图二)
        use_three_images = False
        logger.info("i️ 使用双图模式 (参考图 + 图二)")

        channel = validate_channel(channel)

        # 构建角色替换 prompt
        prompt = build_role_swap_prompt()
        logger.info(f"📸 角色替换模式")

        # 三图/双图输入生成
        if use_three_images:
            logger.info("🚀 wan2.7-image 生成中 (三图输入:参考图 + 图二 + 图三)...")
            model_name, image_url = generate_role_swap_image_three(ref_path, character_path, character_ref_2, prompt, api_key)
        else:
            logger.info("🚀 wan2.7-image 生成中 (双图输入:参考图 + 图 2)...")
            model_name, image_url = generate_role_swap_image(ref_path, character_path, prompt, api_key)

        if not image_url:
            logger.error("生成失败")
            return False

        # 发送生成的图片
        if channel:
            effective_target = target or os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, model_name, effective_target):
                logger.info("发送成功")
                return True
            else:
                logger.error("发送失败")
                return False
        return True

    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"错误:{e}")
        return False
    except Exception as e:
        logger.error(f"错误:{e}")
        return False


if __name__ == "__main__":
    import fcntl

    LOCK_FILE = str(config.get_temp_dir() / "selfie_task.lock")
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    if len(sys.argv) < 2:
        print("用法:")
        print("  角色替换:python3 selfie_v2.py --role-swap <参考图路径> [频道] [配文] [target]")
        print("  图像编辑:python3 selfie_v2.py --edit <图片路径> <编辑指令> [频道] [配文] [target]")
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

    elif sys.argv[1] == '--edit' and len(sys.argv) >= 4:
        # 图像编辑:原图 + 编辑指令
        source_image = sys.argv[2]
        edit_instruction = sys.argv[3]
        channel = sys.argv[4] if len(sys.argv) > 4 else 'feishu'
        caption = sys.argv[5] if len(sys.argv) > 5 else '编辑完成~'
        target = sys.argv[6] if len(sys.argv) > 6 else None
        logger.info(f'🎨 图像编辑模式:{edit_instruction}')
        from pathlib import Path
        success = generate_edit_image(Path(source_image), edit_instruction, caption, channel, target)
        sys.exit(0 if success else 1)
    else:
        print("用法:")
        print("  角色替换:python3 selfie_v2.py --role-swap <参考图路径> [频道] [配文] [target]")
        print("  图像编辑:python3 selfie_v2.py --edit <图片路径> <编辑指令> [频道] [配文] [target]")
        sys.exit(1)
