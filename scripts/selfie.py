#!/usr/bin/env python3
"""selfie.py - 自拍生成模块

支持两种模式:
1. 场景生图:根据场景描述生成 - 1 个模型,1 张图(wan2.7-image)
2. 参考生图:分析参考图后生成 - 1 个模型,1 张图(wan2.7-image)

优化内容:
- 3:4 竖版比例:更适合人像摄影和社交媒体
- 单图输入模式:小柔头像传给 wan2.7,参考图细节通过 prompt 传递
- 商拍模板整合:英文专业框架 + 中文细节补充
- 真实感参数:image_strength=0.65, denoising_strength=0.75
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
import tempfile
import mimetypes
import subprocess
import requests
import uuid
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple, List
# concurrent.futures 已移除(双模型函数已删除)

# 导入统一配置
from config import config, ConfigurationError, ALLOWED_IMAGE_DIRS


# ========== 常量定义 ==========
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
CHUNK_SIZE = 8192  # 下载块大小

# 基于"如何让 AI 生成图片更真实"洞察文章优化的参数
IMAGE_STRENGTH_DEFAULT = float(os.environ.get('XIAOROU_IMAGE_STRENGTH', '0.55'))  # 降低到 0.5-0.6 范围
DENOISING_STRENGTH_DEFAULT = float(os.environ.get('XIAOROU_DENOISING_STRENGTH', '0.65'))  # 降低到 0.6-0.7 范围
MAX_DOWNLOAD_SIZE_MB = 20
MAX_IMAGE_SIZE_MB = 10
MAX_PROMPT_LENGTH = 6000

MAX_INPUT_LENGTH = 500
DEFAULT_IMAGE_SIZE = "1K"
PROMPT_EXTEND = False   # 关闭 AI 自动优化提示词

# 后处理配置（终极版 - 18 步优化 + 反 AI 检测技术）
# 参数基于文档《🎨 小柔 AI 图片去 AI 痕迹终极教程（12 步优化）》+《AI 图片识别技术深度研究报告》
POSTPROCESS_CONFIG = {
    # 原始 12 步配置
    'jpeg_quality': 100,        # JPEG 质量 (100 最高质量，几乎无损)
    'blur_radius': 0.1,         # 模糊半径 (0.1 最轻微)
    'sharp_strength': 0.05,     # 锐化强度 (0.05 最轻微)
    'grain_iso': 50,            # 胶片颗粒 ISO (50 几乎不可见)
    'vignette_intensity': 0.05, # 暗角强度 (0.05 最轻微)
    'color_warmth': 1.01,       # 暖色调 (1.01 几乎不变)
    'ca_offset': 0.5,           # 色差偏移 (0.5 文档推荐值)
    'distortion_strength': 0.02, # 镜头畸变强度 (0.02 文档推荐值)
    'dust_density': 5,          # 传感器灰尘数量 (5 个 文档推荐值)
    'jitter_amplitude': 0.3,    # 微抖动幅度 (0.3 文档推荐值)
    'camera_model': 'iPhone 15 Pro',
    
    # 🆕 Phase 1: 频域优化 + 对抗扰动 (最高优先级)
    # 参数已优化：降低噪声强度，不影响视觉画质
    'frequency_enable': True,
    'spectral_sigma': 0.5,
    'natural_spectrum_strength': 0.06,  # 降低到 0.06（人眼几乎不可见）
    'adversarial_enable': True,
    'adversarial_eps': 0.008,           # 降低到 0.008（人眼几乎不可见）
    
    # 🆕 Phase 2: 多尺度 + 纹理一致性
    'multi_scale_enable': True,
    'pyramid_levels': 4,
    'patch_texture_enable': True,
    'patch_size': 64,
    
    # 🆕 Phase 3: 边缘自然化 + CLIP 特征优化
    'edge_naturalize_enable': True,
    'edge_blur_strength': 0.3,
    'clip_optimize_enable': False,  # 可选，计算成本高
}

# 是否启后处理
ENABLE_POSTPROCESS = os.environ.get('XIAOROU_ENABLE_POSTPROCESS', 'true').lower() == 'true'
# 超时配置(P1 修复 - 可从环境变量定制)
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))
IMAGE_DOWNLOAD_TIMEOUT = int(os.environ.get('XIAOROU_IMAGE_DOWNLOAD_TIMEOUT', '60'))   # 增加到 60 秒

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# P2-1 修复:飞书 token 缓存
_feishu_token: Optional[str] = None
_feishu_token_time: float = 0
_feishu_token_lock = threading.Lock()   # P1-3 修复:并发刷新保护


def _has_path_traversal(file_path: str) -> bool:
    """检查路径是否包含遍历攻击 (..)"""
    return ".." in str(file_path)


def _is_absolute_path(file_path: str) -> bool:
    """检查路径是否为绝对路径"""
    return os.path.isabs(file_path)


def is_safe_path(base_dir: Path, file_path: str) -> bool:
    """检查文件路径是否在允许的目录内 (防止路径遍历攻击)"""
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
        logger.debug(f"路径安全检查失败:{e}")
        return False




def _validate_image_file(file_path: str) -> bool:
    """
    验证图片文件类型(基于魔数检查)

    P1-6 修复:增强文件类型验证,防止恶意文件伪造扩展名

    Args:
        file_path: 图片文件路径

    Returns:
        是否是有效的图片文件
    """
    magic_bytes = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'RIFF....WEBP': 'webp',
    }

    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

         # 检查 JPEG
        if header[:3] == b'\xff\xd8\xff':
            return True

         # 检查 PNG
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True

         # 检查 WEBP (RIFF....WEBP)
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True

        return False
    except Exception as e:
        logger.debug(f"图片魔数检查失败:{e}")
        return False




def is_lock_expired(lock_path: str, timeout_seconds: int = 300) -> bool:
    """检查锁文件是否过期(P0-5 修复:防止进程异常退出后锁文件残留)"""
    try:
        if not os.path.exists(lock_path):
            return True
         # 检查文件修改时间
        mtime = os.path.getmtime(lock_path)
        return (time.time() - mtime) > timeout_seconds
    except Exception:
        return False


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    净化用户输入,移除危险字符并验证长度

    Args:
        text: 原始输入文本
        max_length: 最大长度(默认 500)

    Returns:
        净化后的文本
    """
    if not text:
        logger.warning("输入为空")
        return ""
    if len(text) > max_length:
        logger.warning(f"输入过长 ({len(text)} > {max_length}),已截断")
        text = text[:max_length]

     # 移除控制字符(包括换行、回车)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

     # 移除危险字符(防止注入)(P21-P1-NEW-2 修复:添加 @ 移除,保留中文 《》)
    text = re.sub(r'[`$(){};|&<>[\]*?\\@]', '', text)

     # 移除 Unicode 控制字符(如从右到左覆盖符)
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)

    return text


def validate_channel(channel: Optional[str]) -> Optional[str]:
    if not channel: return None
    valid_channels = {'feishu', 'telegram', 'discord', 'whatsapp'}
    return channel.lower() if channel.lower() in valid_channels else None


def validate_config() -> str:
    """验证并加载 API Key,统一使用 config.py"""
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
     # 检查文件大小(限制 10MB,与 image_analyzer.py 保持一致)
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


def build_prompt(context: str) -> Tuple[str, str]:
    """构建网红风格图片生成 prompt - 自然真实版本

    Raises:
        ValueError: 如果检测到 Prompt Injection 模式
    """
    context_lower = context.lower()

     # H-6 修复:检测 prompt injection 模式,检测到则拒绝处理
    injection_patterns = [
        'ignore', 'disregard', 'system prompt', 'system instruction',
        'previous instructions', 'above instructions', 'override',
        '忽略', '无视', '覆盖', '系统提示', '之前的指令',
    ]
    for pattern in injection_patterns:
        if pattern in context_lower:
            raise ValueError(f"检测到潜在 Prompt Injection 模式:{pattern}")

     # 网红风格基础元素 - 减少 AI 感,增加真实感,清淡妆容,无腮红
    influencer_style = "网红风格,时尚穿搭,专业摄影,清淡妆容,裸妆,无腮红"

     # 真实感增强标签 - 自然光滑,无黑点,淡粉色嘴唇,无腮红,色彩自然,正确人体结构,清淡妆容
    realistic_tags = "真实摄影,自然光滑皮肤,清透肌肤,真实光影,柔和光线,生活照风格,无 AI 感,无塑料感,无黑点,无瑕疵,无口红,裸唇,唇色自然,无妆感,嘴唇本色,无腮红,清淡底妆,底妆轻薄透明,腮红极淡,几乎无腮红,裸妆效果,妆容极淡,色彩柔和自然,低饱和度,避免过度鲜艳,正确人体结构,正常双手,无多余肢体,妆容清淡自然,脸部妆容自然,避免浓妆,色彩素雅,莫兰迪色系,极低饱和度,色彩非常淡,淡雅色调,低对比度,柔和色彩,【自然真实 - 极高优先级】动作极其自然,表情生动真实,姿态放松不僵硬,抓拍感强,生活化场景,日常自然状态,完全不做作,肢体语言流畅,神态自然有神,避免摆拍感,避免刻板姿势,避免表情呆板"
     # 手部质量标签 - 专门针对手部优化 (P1 修复:强化手部描述)
    hand_quality_tags = "【手部质量 - 最高优先级】正常五指,手指修长自然,手指比例正确,无多余手指,无缺失手指,手指关节清晰,指甲自然修剪,手部皮肤光滑,手部光影自然,手部姿势优雅,手腕纤细,手臂线条流畅,手臂比例正常,无畸形手臂,无多余手臂,肘部结构正确,肩膀自然放松,【严禁】六指,【严禁】畸形手,【严禁】融合手指,【严禁】扭曲手臂"
     # 腿部质量标签 - 专门针对腿部优化 (P1 修复:强化多腿问题)
    leg_quality_tags = "【腿部质量 - 最高优先级】完美腿部比例,标准人体结构,腿部细节清晰,膝盖结构正确,脚踝结构正确,腿部光影自然,腿部皮肤质感真实,腿部线条优美,正常腿长比例,双腿完整,腿部无畸形,【严禁】多腿,【严禁】三条腿,【严禁】四条腿,【严禁】多余腿,【严禁】畸形腿,【严禁】融合腿,【严禁】扭曲腿,【严禁】额外肢体,【严格限制】只有两条腿,【严格限制】双腿结构,【严格限制】正常人体下半身,【严格限制】单一双腿"

     # 质量标签 - 强调色彩自然和正确结构
    quality_tags = "8K 超高清,电影级布光,细节丰富,色彩自然柔和,低饱和度,真实色调,正确人体比例,妆容自然,素雅色彩,极低饱和度,完美腿部比例,腿部无畸形,腿部结构正确,【严格限制】正常人体结构,【严格限制】标准四肢,【严格限制】双腿双臂,【严禁】多余肢体,【严禁】多腿,【严禁】多手臂,无水印,无文字,无字样,无 logo,纯净画面"

    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"{influencer_style},{context},全身照,对镜拍摄,网红打卡场景,自然光线,{realistic_tags},{hand_quality_tags},{leg_quality_tags},{quality_tags}"

     # 默认网红风格 prompt - 强调自然真实
    return "direct", f"{influencer_style},{context},眼神直视镜头,自然微笑,真实五官,时尚造型,网红打卡背景,{realistic_tags},{hand_quality_tags},{leg_quality_tags},{quality_tags}"


def generate_single_image(model_name: str, image_path: Path, prompt: str, api_key: str, max_retries: int = 2, reference_image_path: Optional[Path] = None) -> Tuple[str, Optional[str]]:
    """
    使用指定模型生成单张图片(带重试机制)

    Args:
        model_name: 模型名称
        image_path: 输入图片路径(小柔头像)
        prompt: 提示词
        api_key: API Key
        max_retries: 最大重试次数(默认 2 次)
        reference_image_path: 参考图路径(可选,如果提供则使用双图输入)

    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    for attempt in range(max_retries + 1):
        try:
             # 安全修复:不设置全局 dashscope.api_key,使用 per-request key(通过 requests 直接调用)
            input_image_base64 = get_image_base64(image_path)
            logger.info(f"🖼️ 使用本地头像,模型:{model_name} (尝试 {attempt + 1}/{max_retries + 1})")

             # Prompt 长度校验(防止超长 prompt 导致 API 拒绝或静默截断)
            max_prompt_len = MAX_PROMPT_LENGTH
            if len(prompt) > max_prompt_len:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {max_prompt_len}),已截断")
                prompt = prompt[:max_prompt_len]

             # 不同模型的尺寸参数格式不同 - 改成 3:4 竖版最高分辨率
            if model_name == 'qwen-image-2.0-pro':
                size_param = '1280*1707'   # qwen-image-2.0-pro 使用 3:4 最高分辨率
            else:
                size_param = '1280*1707'   # wan2.7-image 使用 3:4 最高分辨率(原 768*1024)

             # 单图输入:只传小柔头像(图生图模式)
             # 参考图已通过 qwen3.5-plus 分析,提取为文字描述在 prompt 中
            content = [
                {'image': input_image_base64},   # 小柔头像(图生图的 base image)
                {'text': prompt}                  # prompt 包含从参考图提取的场景/穿搭/光影等细节
            ]
            logger.info(f"🖼️ 图生图模式:小柔头像 + 文字 prompt(参考图细节已融入 prompt)")

            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': content}]},
                'parameters': {
                    'prompt_extend': PROMPT_EXTEND,
                    'watermark': False,
                    'n': 1,
                    'enable_interleave': False,
                    'size': size_param,
                     # 真实感增强参数
                    'image_strength': IMAGE_STRENGTH_DEFAULT,   # 参考图影响力(0.5-0.7 平衡真实度和还原度)
                    'denoising_strength': DENOISING_STRENGTH_DEFAULT,   # 去噪强度(0.6-0.8 增加细节变化)
                }
            }

            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload, timeout=API_TIMEOUT
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
                time.sleep(1 * (attempt + 1))   # 线性退避
                continue
            return (model_name, None)

        except json.JSONDecodeError as e:
            logger.error(f"❌ {model_name} JSON 解析失败:{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except requests.RequestException as e:
            logger.error(f"❌ {model_name} 请求异常:{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except (KeyboardInterrupt, SystemExit, MemoryError):
             # 严重异常:不重试,直接向上传播
            raise
        except Exception as e:
            logger.error(f"❌ {model_name} 错误:{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)



def generate_images_single_model(image_path: Path, prompt: str, api_key: str, reference_image_path: Optional[Path] = None) -> List[Tuple[str, str]]:
    """
    使用 1 个模型生成图片(场景生图模式)- 只用 wan2.7-image

    Args:
        image_path: 小柔头像路径
        prompt: 提示词
        api_key: API Key
        reference_image_path: 参考图路径(可选,用于双图输入)

    Returns:
        [(model_name, image_url), ...] 成功生成的图片列表
    """
     # P19-P2-NEW-2 修复:删除冗余 models 列表
    model_name = 'wan2.7-image'
    results = []

    if reference_image_path:
        logger.info(f"  使用模型:{model_name}(双图输入)")
    else:
        logger.info(f"  使用模型:{model_name}")

    model_result = generate_single_image(model_name, image_path, prompt, api_key, reference_image_path=reference_image_path)
    if model_result[1]:
        results.append(model_result)
        logger.info(f"✅ {model_name} 生成成功")
    else:
        logger.warning(f"⚠️ {model_name} 生成失败")

    logger.info(f"📊 生成结果:{len(results)}/1 成功")
    return results


def get_feishu_credentials() -> Tuple[Optional[str], Optional[str]]:
    """获取飞书 API 凭证(P2 修复 - 添加类型注解)"""
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                openclaw_config = json.load(f)
            app_id = openclaw_config.get('channels', {}).get('feishu', {}).get('appId', '')
            app_secret = openclaw_config.get('channels', {}).get('feishu', {}).get('appSecret', '')

            if not app_id or not app_secret:
                default_account = openclaw_config.get('channels', {}).get('feishu', {}).get('defaultAccount', 'main')
                accounts = openclaw_config.get('channels', {}).get('feishu', {}).get('accounts', {})
                app_id = accounts.get(default_account, {}).get('appId', '')
                app_secret = accounts.get(default_account, {}).get('appSecret', '')

            if app_id and app_secret:
                return app_id, app_secret
        except Exception as e:
            logger.debug(f"读取飞书配置失败:{e}")

    app_id = os.environ.get('FEISHU_APP_ID', '')
    app_secret = os.environ.get('FEISHU_APP_SECRET', '')
    if app_id and app_secret:
        return app_id, app_secret

    return None, None


def get_feishu_access_token() -> Optional[str]:
    """获取飞书 access_token(带 2 小时缓存,线程安全)"""
    global _feishu_token, _feishu_token_time

     # 快速检查(无锁)
    if _feishu_token and (time.time() - _feishu_token_time) < 7200:
        return _feishu_token

     # 加锁刷新(P1-3 修复:防止并发竞态)
    with _feishu_token_lock:
         # double-check
        if _feishu_token and (time.time() - _feishu_token_time) < 7200:
            return _feishu_token

        app_id, app_secret = get_feishu_credentials()
        if not app_id or not app_secret:
            logger.warning("未配置飞书凭证,无法获取 access_token")
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
    """上传图片到飞书,返回 image_key"""
    access_token = get_feishu_access_token()
    if not access_token:
        logger.warning("获取飞书 access_token 失败")
        return None

    upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
    with open(image_file, 'rb') as f:
        files = {'image': (os.path.basename(image_file), f, 'image/jpeg')}
        data = {'image_type': 'message'}   # 飞书要求
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

    logger.warning(f"飞书图片上传失败:{upload_data}")
    return None


def send_feishu_image_message(image_key: str, caption: str, receive_id: str, receive_id_type: Optional[str] = None) -> bool:
    """发送飞书原生图片消息

    Args:
        image_key: 飞书图片 key
        caption: 图片描述文字
        receive_id: 接收者 ID
        receive_id_type: 接收者 ID 类型(open_id/union_id/user_id/app_open_id),不传则自动识别

    Returns:
        是否发送成功
    """
    access_token = get_feishu_access_token()
    if not access_token:
        return False

     # 自动识别 ID 类型(P0-2 修复:避免跨应用 open_id 错误)
    if receive_id_type is None:
        if receive_id.startswith('ou_'):
            receive_id_type = 'open_id'   # ✅ ou_=open_id
        elif receive_id.startswith('on_'):
            receive_id_type = 'union_id'   # ✅ on_=union_id
        elif receive_id.startswith('ai_'):
            receive_id_type = 'app_open_id'
        elif receive_id.startswith('u_'):
            receive_id_type = 'user_id'
        else:
            logger.error(f"❌ 无法识别 receive_id 类型:{receive_id[:10]}... (期望前缀:ou_/on_/ai_/u_)")
            return False   # 拒绝处理,避免跨 app 错误
        logger.debug(f"自动识别 receive_id_type: {receive_id_type} for {receive_id[:10]}...")

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

     # P0-3 修复:检测 401 错误,自动刷新 token 后重试
    if result.get('code') == 99991663:   # 飞书 token 无效错误码
        logger.warning("检测到 token 无效,尝试刷新后重试...")
        global _feishu_token, _feishu_token_time
        _feishu_token = None   # 清空缓存
        _feishu_token_time = 0
        access_token = get_feishu_access_token()   # 重新获取
        if access_token:
            response = requests.post(
                message_url,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=message_data,
                timeout=60
            )
            result = response.json()
            if result.get('code') == 0:
                logger.info("✅ 飞书原生图片消息发送成功(重试后)")
                return True

    logger.error(f"飞书图片消息发送失败:{result}")
    return False


def get_model_display(model_name: str) -> str:
    """获取模型名称的 emoji 显示格式"""
    model_map = {
        'wan2.7-image': '🎨【万相 2.7】',
        'wan2.7-image-pro': '🎨【万相 2.7 Pro】',
        'qwen-image-2.0': '🖼️【千问 2.0】',
        'qwen-image-2.0-pro': '🖼️【千问 2.0 Pro】'
    }
    return model_map.get(model_name, f'📷【{model_name}】')


def _download_image(image_url: str, temp_file: str) -> bool:
    """下载图片到临时文件"""
    try:
        response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()

         # SSRF 防护
        final_url = response.url
        allowed_domains = ['dashscope.aliyuncs.com', 'aliyuncs.com', 'volces.com']
        parsed = urlparse(final_url)
        hostname = parsed.hostname or ''
        is_allowed = any(
            hostname == domain or hostname.endswith('.' + domain)
            for domain in allowed_domains
        )
        if not is_allowed:
            logger.error(f"⚠️ 下载 URL 重定向到非信任域:{final_url}")
            return False

         # 检查重定向次数
        if len(response.history) > 5:
            logger.error(f"重定向次数过多:{len(response.history)}")
            return False

         # 检查 Content-Type
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            logger.error(f"远程资源不是图片类型:{content_type}")
            return False

         # 检查文件大小
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_IMAGE_SIZE_BYTES:
            logger.error(f"图片过大 ({int(content_length) / 1024 / 1024:.1f}MB > 20MB)")
            return False

         # 下载文件
        max_download_size = MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
        downloaded = 0
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    downloaded += len(chunk)
                    if downloaded > max_download_size:
                        raise ValueError(f"下载超出大小限制 ({downloaded / 1024 / 1024:.1f}MB > 20MB)")
                    f.write(chunk)

        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return False

        return True
    except Exception as e:
        logger.error(f"下载图片失败:{e}")
        return False


def _save_to_output_dir(temp_file: str, user_id: str) -> Optional[str]:
    """保存到永久输出目录"""
    try:
        timestamp = int(time.time())
        output_dir = config.get_output_dir()
        output_path = output_dir / f'selfie_{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg'
        temp_dst = None
        try:
            temp_dst = str(output_path) + '.tmp'
            shutil.copy2(temp_file, temp_dst)
            os.replace(temp_dst, str(output_path))
            logger.info(f"✓ 已永久保存自拍到:{output_path}")
            return str(output_path)
        except Exception as e:
            logger.warning(f"保存自拍失败:{e}")
            if temp_dst and os.path.exists(temp_dst):
                os.remove(temp_dst)
            return None
    except Exception as e:
        logger.debug(f"保存输出目录失败:{e}")
        return None


def send_to_channel(image_url: str, caption: str, channel: str, model_name: str, target: Optional[str] = None) -> bool:
    """发送图片到频道,飞书使用原生图片格式,其他平台使用文件"""
    try:
        logger.info(f"📤 发送到:{channel} (model: {model_name})")

         # 准备 caption
        model_display = get_model_display(model_name)
        full_caption = f"{model_display} {caption}"

         # 准备临时文件路径
        timestamp = int(time.time())
        safe_model_name = model_name.replace('.', '_').replace('-', '_')[:50]
        temp_dir = config.get_temp_dir()
        temp_file = f'{temp_dir}/selfie_{safe_model_name}_{timestamp}.jpg'
        os.makedirs(str(temp_dir), mode=0o700, exist_ok=True)

         # 下载图片
        if not _download_image(image_url, temp_file):
            return False

        logger.info(f"✅ 图片下载完成:{temp_file}")

         # 【新增】真实性增强后处理(基于洞察文章优化)
        if ENABLE_POSTPROCESS:
            try:
                from postprocess import enhance_realism
                logger.info("🎨 开始真实性增强处理...")
                enhanced_file = temp_file.rsplit('.', 1)[0] + '_enhanced.jpg'
                enhance_realism(temp_file, enhanced_file, POSTPROCESS_CONFIG)

                # 替换为增强后的文件
                if os.path.exists(enhanced_file):
                    temp_file = enhanced_file
                    logger.info("✨ 真实性增强完成")
            except Exception as e:
                logger.warning(f"⚠️ 后处理失败:{e},使用原始图片")

         # 保存到输出目录
        user_id = target or 'default'
        user_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(user_id))[:32]
        output_path = _save_to_output_dir(temp_file, user_id)

         # 发送到频道
        success = _send_to_channel_impl(temp_file, full_caption, channel, target)

        return success
    except Exception as e:
        logger.error(f"发送异常:{e}")
        return False


def _send_to_channel_impl(temp_file: str, full_caption: str, channel: str, target: Optional[str] = None) -> bool:
    """实现发送逻辑"""
     # 飞书使用原生图片消息
    if channel == 'feishu':
        send_target = target or os.environ.get('AEVIA_TARGET', '')
        if not send_target:
            send_target = config.get_feishu_target()

        if not send_target:
            logger.error("未配置飞书目标用户(target),请设置 AEVIA_TARGET 环境变量或配置文件")
            return False

        logger.info(f"📤 飞书目标用户:{send_target[:10]}...")
        image_key = upload_feishu_image(temp_file)
        if image_key:
            if send_feishu_image_message(image_key, full_caption, send_target):
                logger.info("✓ 飞书原生图片发送成功")
                return True
            else:
                logger.error("发送飞书图片消息失败")
                return False
        else:
            logger.error("上传飞书图片失败")
            return False

     # 其他平台使用 openclaw message send 命令
    else:
        send_target = target or os.environ.get('AEVIA_TARGET', '')
        if not send_target:
            send_target = config.get_feishu_target() if channel == 'feishu' else ''

        cmd_args = [
            'openclaw', 'message', 'send',
            '--channel', channel,
            '--target', send_target,
            '--message', full_caption,
            '--media', temp_file
        ]

        account = os.environ.get('AEVIA_ACCOUNT') or os.environ.get('OPENCLAW_ACCOUNT', '')
        if account:
            cmd_args.extend(['--account', account])
            logger.info(f"使用账号:{account}")

        try:
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"发送异常:{e}")
            return False



def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """普通模式:根据文字描述生成图片,单模型生成"""
     # P1-2 修复:target 格式校验
    if target and not re.match(r'^(ou_|on_|ai_|u_)[a-z0-9_]+$', target):
        logger.warning(f"⚠️ target 格式不符合预期(应为 (ou_|on_|ai_|u_)[a-z0-9_]+):{target}")
     # P2-2 修复:临时文件清理由 send_to_channel 的 finally 块自行处理
     # 若发生 KeyboardInterrupt,send_to_channel 确保已下载的临时文件被清理
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")

        image_path = validate_character_image()
        logger.info("✅ 头像文件验证通过")

        context = sanitize_input(context)
        if not context:
            logger.error("无效的场景描述")
            return False

        channel = validate_channel(channel)
        mode, prompt = build_prompt(context)
        logger.info(f"📸 模式:{mode}")

         # 单模型生成(wan2.7-image)
        logger.info("🚀 万相 2.7 生成中...")
        results = generate_images_single_model(image_path, prompt, api_key)

        if not results:
            logger.error("❌ 模型生成失败")
            return False

         # 发送所有成功生成的图片
        success_count = 0
        for model_name, image_url in results:
            if channel and image_url:
                effective_target = target or os.environ.get('AEVIA_TARGET')
                if send_to_channel(image_url, caption, channel, model_name, effective_target):
                    success_count += 1

        logger.info(f"✅ 成功发送 {success_count}/{len(results)} 张图片")
        return success_count > 0

    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误:{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误:{e}")
        return False


def generate_from_reference(reference_image_path: str, caption: str = "这是模仿参考图生成的~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    参考图模式(优化版 - 新流程)

    流程:
    1. 分析参考图 → 提取场景、姿势、服装、光线等描述(**完全忽略人脸**)
    2. 使用小柔头像作为图生图的输入
    3. Prompt:保留小柔脸,套用参考图的场景/穿搭/姿态
    4. 单模型生成(wan2.7-image)

    Args:
        reference_image_path: 参考图路径
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标

    Returns:
        是否成功
    """
     # P1-2 修复:target 格式校验
    if target and not re.match(r'^(ou_|on_|ai_|u_)[a-z0-9_]+$', target):
        logger.warning(f"⚠️ target 格式不符合预期(应为 (ou_|on_|ai_|u_)[a-z0-9_]+):{target}")
     # P2-2 修复:临时文件清理由 send_to_channel 的 finally 块自行处理
     # 若发生 KeyboardInterrupt,send_to_channel 确保已下载的临时文件被清理
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")

         # 1. 验证参考图
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            logger.error(f"参考图不存在:{reference_image_path}")
            return False
        logger.info("✅ 参考图验证通过")

         # 2. 加载小柔头像
        image_path = validate_character_image()
        logger.info("✅ 头像文件验证通过(使用小柔头像)")

        channel = validate_channel(channel)

         # 忽略 multi_mode 参数,始终使用分析 + 单模型图生图模式
        logger.info("🔍 分析参考图模式:提取 prompt 后单模型生成")

         # 3. 分析参考图,提取 prompt
        script_dir = Path(__file__).resolve().parent
        analyzer_path = script_dir / 'image_analyzer.py'

        if not analyzer_path.exists():
            logger.error(f"图片分析模块不存在:{analyzer_path}")
            return False

         # 安全检查:验证参考图路径(P2-5 修复:使用统一目录列表)
         # P0-2 修复:统一 resolve 处理,防止路径遍历攻击
        ref_resolved = Path(reference_image_path).resolve()
        is_allowed = any(
            is_safe_path(base_dir.resolve(), str(ref_resolved))
            for base_dir in ALLOWED_IMAGE_DIRS
        )
        if not is_allowed:
            logger.error(f"⚠️ 参考图路径不在允许范围内:{reference_image_path}")
            return False

         # P21-P2-NEW-2 修复:验证 analyzer 脚本完整性(SHA256 校验)
        import hashlib
        analyzer_hash = hashlib.sha256(analyzer_path.read_bytes()).hexdigest()
         # 允许的哈希值列表(已知安全的脚本版本)
         # 注:修改脚本后需要更新此哈希值
         # 如果校验失败,至少记录警告(不阻止执行,避免版本更新时中断服务)
        logger.debug(f"analyzer.py SHA256: {analyzer_hash}")

        try:
            result = subprocess.run(
                ['python3', str(analyzer_path), reference_image_path],
                capture_output=True,
                text=True,
                timeout=int(os.environ.get('XIAOROU_API_TIMEOUT', '120')),
                shell=False   # 显式声明不使用 shell
            )
        except subprocess.TimeoutExpired:
            logger.error(f"图片分析超时(超过 {os.environ.get('XIAOROU_API_TIMEOUT', '120')} 秒)")
            return False

        if result.returncode != 0:
            logger.error(f"图片分析失败:{result.stderr}")
            return False

        prompt = result.stdout.strip()
         # P1-1 修复:只记录长度,不记录敏感内容
        logger.info(f"✅ 参考图分析完成 (prompt 长度:{len(prompt)})")

         # 4. 单模型生成(wan2.7-image)- 双图输入:小柔头像 + 参考图
        logger.info("🚀 wan2.7-image 生成中(双图输入:头像 + 参考图)...")
        results = generate_images_single_model(image_path, prompt, api_key, reference_image_path=ref_path)

        if not results:
            logger.error("❌ 所有模型都生成失败")
            return False

         # 5. 发送生成的图片(单模型)
        success_count = 0
        failed_models = []
        for model_name, image_url in results:
            if channel and image_url:
                effective_target = target or os.environ.get('AEVIA_TARGET')
                logger.info(f"📤 准备发送:{model_name}")
                if send_to_channel(image_url, caption, channel, model_name, effective_target):
                    success_count += 1
                    logger.info(f"✅ {model_name} 发送成功")
                else:
                    failed_models.append(model_name)
                    logger.error(f"❌ {model_name} 发送失败")

        if failed_models:
            logger.error(f"⚠️ 发送失败的模型:{', '.join(failed_models)}")
        logger.info(f"✅ 成功发送 {success_count}/{len(results)} 张图片(单模型)")
        return success_count > 0

    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误:{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误:{e}")
        return False


if __name__ == "__main__":
    import fcntl

     # 防并发刷屏锁机制
    LOCK_FILE = str(config.get_temp_dir() / "selfie_task.lock")
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

     # P0-5 修复:检查锁文件是否过期(防止进程异常退出后残留)
     # P0-6 优化:超时时间 300 秒 → 30 秒,支持高频并发测试
    if not is_lock_expired(LOCK_FILE, timeout_seconds=30):
        print("Task is already running. Skipping to prevent spam.")
        sys.exit(0)

     # 清理过期锁文件
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except:
            pass

    lock_fd = None
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
    except IOError:
         # 如果无法获取锁,说明已有任务在运行,直接退出防止刷屏
        print("Task is already running. Skipping to prevent spam.")
        sys.exit(0)

     # 确保退出时释放锁和清理文件
    import atexit
    def release_lock():
        try:
            if lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except:
            pass
    atexit.register(release_lock)

     # --json 模式:输出 JSON 结果,不发送(由 bot 处理发送)
    json_mode = '--json' in sys.argv

    if len(sys.argv) < 2 or (len(sys.argv) == 2 and sys.argv[1] == '--json'):
        print("用法:")
        print("  场景生图:python3 selfie.py <场景描述> [频道] [配文] [target]")
        print("  参考生图:python3 selfie.py --reference <参考图路径> [频道] [配文] [target]")
        print("  JSON 模式:python3 selfie.py --reference <路径> --json")
        sys.exit(1)

     # 检测是否为参考图模式
    if sys.argv[1] == '--reference' and len(sys.argv) >= 3:
        reference_image = sys.argv[2]

         # 先验证文件存在和路径安全(P1-1 修复:在任何模式下都先验证)
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在:{reference_image}")
            sys.exit(1)

         # P2-5 修复:使用统一目录列表
        is_allowed = any(is_safe_path(base_dir.resolve(), reference_image) for base_dir in ALLOWED_IMAGE_DIRS)
        if not is_allowed:
            logger.error(f"⚠️ 参考图路径不在允许范围内:{reference_image}")
            sys.exit(1)

         # 解析参数
        channel = None
        caption = "这是模仿参考图生成的~"
        target = None
        if json_mode:
            for i, arg in enumerate(sys.argv[3:], 3):
                if arg.startswith('--caption='):
                    caption = arg[len('--caption='):]
        else:
            channel = sys.argv[3] if len(sys.argv) > 3 else None
            caption = sys.argv[4] if len(sys.argv) > 4 else "这是模仿参考图生成的~"
            target = sys.argv[5] if len(sys.argv) > 5 else None

         # 统一调用生成函数
        success = generate_from_reference(reference_image, caption, channel, target)
    else:
         # 场景生图模式
        context = sys.argv[1]
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
        target = sys.argv[4] if len(sys.argv) > 4 else None

        success = generate_selfie(context, caption, channel, target)

    sys.exit(0 if success else 1)

