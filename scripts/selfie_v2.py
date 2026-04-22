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
    构建角色替换 prompt - v6.2.0 完整版
    
    Args:
        reference_description: 参考图的额外描述 (可选)
    
    Returns:
        完整的角色替换 prompt
    """
    # 核心指令：角色替换（图 1=小柔，图 2=参考图）
    instruction = """【角色替换指令 - 最高优先级】
这是一张"角色替换"生成任务：
- **图 1（小柔头像）**：提供人物身份、脸部特征 → **100% 使用这张脸**
- **图 2（参考图）**：提供场景、服装、姿势、光影、构图 → **人脸完全忽略**
- 生成目标：保持**图 2**的一切内容（场景/服装/姿势/光影/构图/色调），**仅将人物替换为图 1 的小柔**

【人脸锁定 - 最高优先级 - 权重 5.0】
- **图 1（小柔）的五官特征 100% 保留，不受图 2 任何影响**
- **图 2（参考图）的人脸完全忽略，只参考姿势/角度**
- **眼睛/鼻子/嘴巴/眉毛/脸型完全使用图 1（小柔）的特征**
- **禁止混合图 2 的脸部特征**
- **禁止图 2 人脸影响生成结果**
- **图 1 的脸部特征完全覆盖图 2 人脸区域**
- **禁止任何马赛克/模糊/雾化/打码效果**
- **禁止任何云雾/烟雾/蒸汽/朦胧效果**
- **脸部必须清晰通透，无烟雾遮挡，无像素化，无朦胧感**
- **画面必须清晰锐利，无雾化无模糊**

【无水印 - 绝对禁止 - 最高权重 5.0】
- **(无水印：5.0)** - 绝对禁止任何形式的水印
- **(无文字：5.0)** - 绝对禁止任何文字、数字、字母
- **(无 logo:5.0)** - 绝对禁止任何 logo、品牌标识
- **(无签名：5.0)** - 绝对禁止签名、用户名、ID 号
- **(无平台标记：5.0)** - 禁止小红书/抖音/微博/Instagram/TikTok 等所有平台水印
- **(忽略参考图水印：5.0)** - **参考图的水印必须完全忽略，不能复制到生成图中**
- **(去除参考图水印：5.0)** - 如果参考图有水印，生成时必须完全去除，不能保留
- **(参考图水印不继承：5.0)** - **参考图的水印不会继承到生成图，必须过滤掉**
- **(纯净画面：4.0)** - 画面必须干净，无任何文字元素
- **(角落无水印：5.0)** - 禁止右下角、左下角、任何角落的水印
- **(无文字叠加：5.0)** - 禁止任何形式的文字叠加、覆盖

【人物身份 - 绝对使用小柔 - 终极权重】
- **必须 100% 使用输入图 2(小柔头像) 的脸部、五官、脸型、神态、发型、发色、发量**
- **发型完全不变**：小柔的发型、刘海、发长、发丝细节、发色完全保留，禁止使用参考图的发型
- **肤色完全一致**：小柔的脸部肤色、颈部肤色、全身肤色必须与输入图 2 完全一致，禁止使用参考图的肤色
- **脸部特征锁定**：眼睛、鼻子、嘴巴、眉毛、耳朵、脸型、下巴轮廓、颧骨完全不变
- **脸部角度匹配**：小柔的脸部角度（正脸/侧脸/低头/抬头）必须与参考图完全一致
- **头部姿态匹配**：头部的偏航角 (yaw)、俯仰角 (pitch)、翻滚角 (roll) 必须匹配参考图
- 禁止使用参考图的脸部特征、发型、肤色
- 禁止混合两张图片的脸部、发型、肤色
- 人物身份必须是小柔，不能变成参考图里的人
- **肤色统一性**：脸部、颈部、手臂、腿部等所有暴露皮肤的肤色必须与小柔头像一致，不能出现色差
- **忽略图 2 的人脸**：图 2(参考图) 的人脸完全忽略，不影响生成结果，仅作为场景/服装/姿势参考
- **光源一致性**：图 1 的脸部必须接受图 2 的光源方向（顺光/侧光/逆光/顶光）
- **肤色融合**：图 1 的脸部肤色要与图 2 的环境光协调，不能有色差
- **阴影融合**：鼻影、眼窝、下巴阴影必须与图 2 的光照方向匹配
- **高光一致**：额头、鼻梁、颧骨的高光位置必须与图 2 的光源位置一致
- **环境光遮蔽**：图 1 与背景的接触处必须有正确的环境光遮蔽（AO）
- **色温统一**：图 1 的脸部色温必须与图 2 的整体色温一致（暖光/冷光）
- **肤色协调**：脸部、颈部、手臂等暴露皮肤的色调必须统一，不能有色差

【保持参考图内容 - 完全不变】
- 服装穿搭：上衣、下装、连衣裙、配饰、鞋子 (完全保持参考图)
- 姿势动作：站姿/坐姿、手部动作、身体角度 (完全保持参考图)
- 场景背景：地点、背景元素、道具 (完全保持参考图)
- 光线色调：光源方向、光线质量、整体色调 (完全保持参考图)
- 构图镜头：景别、拍摄角度、景深效果 (完全保持参考图)
- 表情神态：微笑/眼神/情绪表达 (保持参考图，但用小柔的脸)
- **唯一例外：参考图的水印必须忽略，不能保留**

【无水印要求 - 最高优先级 - 必须遵守】
- 禁止任何形式的水印、logo、文字、品牌标识、签名
- 禁止平台水印（小红书、抖音、微博、Instagram、TikTok 等）
- 禁止角落水印、右下角水印、用户名水印、数字 ID 水印
- 禁止文字叠加、文字覆盖、任何位置的文字
- 画面必须干净纯净，无任何文字元素
- **如参考图有水印，生成时必须完全去除，不能保留**
- **参考图的水印不会继承到生成图，必须过滤掉**
- **忽略参考图水印，只保留参考图的场景/服装/姿势**

【质量要求】
- 真实摄影质感，无 AI 感，无塑料感
- 人物与背景自然融合，光影统一
- 手部完整，手指数量正确
- 腿部比例正常，结构正确
- **头身比例协调：头部大小与身体比例正确，头身比 1:8-1:9**
- **小脸效果：脸部小巧精致，不过大，瓜子脸**
- **头部自然：头部大小正常，不过大不过小，与身体协调**
- **人体结构正确：头颈肩比例自然，身体各部分比例协调**
- 8K 超高清，专业人像摄影"""

    # 基础风格
    base_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，自然真实"

    # 真实感标签
    realistic_tags = """真实摄影，自然皮肤纹理，可见毛孔，轻微皮肤瑕疵，
真实相机噪点，ISO 400 胶片颗粒，自然光线，柔和阴影，
Canon EOS R5 拍摄，85mm f/1.8 镜头，Kodak Portra 400 胶片，
自然光滑皮肤，清透肌肤，真实光影，生活照风格，无 AI 感"""

    # 质量标签 - 精简版 (避免截断)
    quality_tags = "8K 超高清，正确人体比例，头身比 1:7-1:8，(无水印：5.0)，(无文字：5.0)，(无 logo:5.0)，(纯净画面：4.0)，(no watermark:5.0)，(no text:5.0)"

    # 反向提示词 - 精简版 (避免截断)
    negative_tags = """避免 AI 感，避免畸形，正常人体结构，比例正确，
避免头身比例失调，避免头部过大过小，避免大脸，避免脸大，
避免脸部角度错误，避免正脸侧脸不匹配，
避免肤色不均，避免脸部颈部色差，避免光源冲突，
(watermark:5.0), (no watermark:5.0), (logo:5.0), (no logo:5.0),
(text:5.0), (no text:5.0), (mosaic:5.0), (no mosaic:5.0),
(smoke:5.0), (fog:5.0), (blur:5.0), (pixelated:5.0), (haze:5.0), (cloudy:5.0), (mist:5.0),
(big head:5.0), (small head:5.0), (head body mismatch:5.0), (big face:5.0), (large face:5.0),
(wrong head size:5.0), (head proportion:5.0), (body proportion:5.0),
(wrong face angle:5.0), (face angle mismatch:5.0), (wrong head pose:5.0),
(worst quality, low quality:1.4), (deformed, distorted:1.3), bad anatomy"""

    full_prompt = f"""{instruction}。

【参考图额外描述】{reference_description if reference_description else "无额外描述"}。

【基础风格】{base_style}。

【真实感】{realistic_tags}。

【质量标签】{quality_tags}。

【反向提示词】{negative_tags}。

【EXTREMELY CRITICAL - 精简版】
**(无水印：5.0) - ABSOLUTELY NO WATERMARK**
**(头身比例协调：5.0) - CORRECT HEAD-BODY PROPORTION (1:7-1:8)**
**(头部大小正常：5.0) - NORMAL HEAD SIZE**
**(光源一致性：5.0) - CONSISTENT LIGHTING**
**(肤色协调：5.0) - SKIN TONE BLENDING: face/neck/arm color unified**
**(无马赛克：5.0) - NO MOSAIC/BLUR/FOG/PIXELATED**
**(无云雾：5.0) - NO HAZE/CLOUDY/MIST/SMOKE**
**(画面清晰：5.0) - CLEAR AND SHARP IMAGE**
**(小脸精致：5.0) - SMALL FACE, DELICATE FACE**
**(头身比 1:8:5.0) - CORRECT HEAD-BODY RATIO 1:8**
**(脸部角度匹配：5.0) - MATCH FACE ANGLE (正脸/侧脸/低头/抬头)**
**(忽略图 2 人脸：5.0) - IGNORE image-2 face**
**(100% 使用图 1 脸：5.0) - 100% USE image-1 face**
**(人脸锁定：5.0) - FACE LOCK: image-1 features 100% preserved**
Keep EVERYTHING from **image-2** (outfit/pose/scene/lighting/face angle), ONLY swap face to **image-1**. 100% identical face, hairstyle, skin tone, face angle from **image-1**. (NO watermark:5.0), (NO mosaic/blur/fog/pixelated:5.0), (CORRECT head-body proportion:5.0), (NORMAL head size:5.0), (CONSISTENT lighting:5.0), (SKIN TONE BLENDING:5.0), (MATCH face angle:5.0), (IGNORE image-2 face:5.0), (100% USE image-1 face:5.0), (FACE LOCK:5.0). **image-1**'s face must match **image-2** face angle (yaw/pitch/roll), blend with **image-2** lighting: same light direction, shadows, highlights, color temperature. Face/neck/arm skin tone must be unified. NO mosaic, NO blur, NO fog, NO pixelated, NO haze, NO cloudy, NO mist, NO smoke. Clear and sharp image. Small face, delicate face, correct head-body ratio 1:8. Head size 1:8-1:9 ratio. **图 1（小柔）的五官特征 100% 保留，不受图 2 任何影响。图 2（参考图）的人脸完全忽略，只参考姿势/角度。眼睛/鼻子/嘴巴/眉毛/脸型完全使用图 1（小柔）的特征。禁止马赛克/模糊/雾化/打码/云雾/朦胧感。画面必须清晰锐利。肤色必须协调统一。小脸精致，头身比 1:8。** (中文：无水印；无马赛克；无云雾；画面清晰；小脸精致；头身比 1:8；**忽略图 2 人脸，100% 用图 1 脸**；光源一致；肤色协调；脸部角度匹配图 2；人脸锁定）"""

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

            # 双图输入：小柔头像 (图 1) + 参考图 (图 2)
            # 优化：小柔头像放图 1，AI 更自然地保持图 1 人脸，参考图 2 风格
            content = [
                {'image': character_base64},      # 图 1: 小柔头像 (人物身份 - 主要参考)
                {'image': reference_base64},      # 图 2: 参考图 (场景/服装/姿势)
                {'text': prompt}                   # 角色替换提示词
            ]
            logger.info(f"🖼️ 双图输入：图 1(小柔) + 图 2(参考) + 文字 prompt")

            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': content}]},
                'parameters': {
                    'prompt_extend': False,
                    'watermark': False,
                    'n': 1,
                    'enable_interleave': False,
                    'size': '1536*2048',  # 3:4 竖版高清
                    # 关键参数：增强图 1(小柔) 的影响力
                    'image_strength': 0.85,  # 0.85 = 85% 保留图 1 特征 (小柔脸)
                    'denoising_strength': 0.35,  # 0.35 = 较低的去噪强度，保持原图特征
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
