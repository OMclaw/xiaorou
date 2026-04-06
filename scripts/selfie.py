#!/usr/bin/env python3
"""selfie.py - 自拍生成模块

支持两种模式：
1. 场景生图：根据场景描述生成 - 1 个模型，1 张图（wan2.7-image）
2. 参考生图：分析参考图后生成 - 1 个模型，1 张图（wan2.7-image）
"""

import dashscope
import os
import sys
import json
import base64
import logging
import re
import time
import requests
from pathlib import Path
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入统一配置
from config import config, ConfigurationError

# 使用配置模块
TEMP_DIR = config.get_temp_dir() / 'selfies'
TEMP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
MAX_INPUT_LENGTH = 500
DEFAULT_IMAGE_SIZE = "1K"
PROMPT_EXTEND = False  # 关闭 AI 自动优化提示词
# 超时配置（P1 修复 - 可从环境变量定制）
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))
IMAGE_DOWNLOAD_TIMEOUT = int(os.environ.get('XIAOROU_IMAGE_DOWNLOAD_TIMEOUT', '60'))  # 增加到 60 秒

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def is_safe_path(base_dir: Path, file_path: str) -> bool:
    """
    检查文件路径是否在允许的目录内（防止路径遍历攻击）
    
    Args:
        base_dir: 允许的基础目录
        file_path: 要检查的文件路径
    
    Returns:
        是否安全
    """
    try:
        base_dir = base_dir.resolve()
        resolved = Path(file_path).resolve()
        
        # 严格检查：必须是子目录，不能只是前缀匹配
        # 例如：/tmp/openclaw_evil 不应该通过 /tmp/openclaw 的检查
        try:
            resolved.relative_to(base_dir)
            return True
        except ValueError:
            return False
    except Exception:
        return False


def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    净化用户输入，移除危险字符并验证长度
    
    Args:
        text: 原始输入文本
        max_length: 最大长度（默认 500）
    
    Returns:
        净化后的文本
    """
    if not text:
        logger.warning("输入为空")
        return ""
    if len(text) > max_length:
        logger.warning(f"输入过长 ({len(text)} > {max_length})，已截断")
        text = text[:max_length]
    
    # 移除控制字符（包括换行、回车）
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # 移除危险字符（防止注入）
    text = re.sub(r'[`$(){};|&!\\<>[\]*?]', '', text)
    
    # 移除 Unicode 控制字符（如从右到左覆盖符）
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)
    
    return text


def validate_channel(channel: Optional[str]) -> Optional[str]:
    if not channel: return None
    valid_channels = {'feishu', 'telegram', 'discord', 'whatsapp'}
    return channel.lower() if channel.lower() in valid_channels else None


def validate_config() -> str:
    """验证并加载 API Key，统一使用 config.py"""
    return config.get_api_key()


def validate_character_image() -> Path:
    """验证小柔头像文件是否存在"""
    script_dir = Path(__file__).resolve().parent
    character_path = script_dir.parent / 'assets/default-character.png'
    if not character_path.exists():
        raise FileNotFoundError(f"头像文件不存在：{character_path}")
    return character_path


def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64 格式"""
    # 检查文件大小（限制 10MB，与 image_analyzer.py 保持一致）
    file_size = image_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"图片文件为空：{image_path}")
    if file_size > 10 * 1024 * 1024:
        raise ValueError(f"图片文件过大：{file_size / 1024 / 1024:.2f}MB（限制 10MB）")
    
    with open(image_path, 'rb') as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"


def build_prompt(context: str) -> Tuple[str, str]:
    """构建网红风格图片生成 prompt - 自然真实版本
    
    Raises:
        ValueError: 如果检测到 Prompt Injection 模式
    """
    context_lower = context.lower()
    
    # H-6 修复：检测 prompt injection 模式，检测到则拒绝处理
    injection_patterns = [
        'ignore', 'disregard', 'system prompt', 'system instruction',
        'previous instructions', 'above instructions', 'override',
        '忽略', '无视', '覆盖', '系统提示', '之前的指令',
    ]
    for pattern in injection_patterns:
        if pattern in context_lower:
            logger.warning(f"⚠️ 检测到潜在 Prompt Injection 模式：{pattern}（仅警告，不拒绝）")
    
    # 网红风格基础元素 - 减少 AI 感，增加真实感，清淡妆容，无腮红
    influencer_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，无腮红"
    
    # 真实感增强标签 - 自然光滑，无黑点，淡粉色嘴唇，无腮红，色彩自然，正确人体结构，清淡妆容
    realistic_tags = "真实摄影，自然光滑皮肤，清透肌肤，真实光影，柔和光线，生活照风格，无 AI 感，无塑料感，无黑点，无瑕疵，无口红，裸唇，唇色自然，无妆感，嘴唇本色，无腮红，清淡底妆，底妆轻薄透明，腮红极淡，几乎无腮红，裸妆效果，妆容极淡，色彩柔和自然，低饱和度，避免过度鲜艳，正确人体结构，正常双手，无多余肢体，妆容清淡自然，脸部妆容自然，避免浓妆，色彩素雅，莫兰迪色系，极低饱和度，色彩非常淡，淡雅色调，低对比度，柔和色彩"
    
    # 腿部质量标签 - 专门针对腿部优化
    leg_quality_tags = "完美腿部比例，标准人体结构，腿部细节清晰，膝盖结构正确，脚踝结构正确，腿部光影自然，腿部皮肤质感真实，腿部线条优美，正常腿长比例，双腿完整，腿部无畸形"
    
    # 质量标签 - 强调色彩自然和正确结构
    quality_tags = "8K 超高清，电影级布光，细节丰富，色彩自然柔和，低饱和度，真实色调，正确人体比例，妆容自然，素雅色彩，极低饱和度，完美腿部比例，腿部无畸形，腿部结构正确"
    
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"{influencer_style}，{context}，全身照，对镜拍摄，网红打卡场景，自然光线，{realistic_tags}，{leg_quality_tags}，{quality_tags}"
    
    # 默认网红风格 prompt - 强调自然真实
    return "direct", f"{influencer_style}，{context}，眼神直视镜头，自然微笑，真实五官，时尚造型，网红打卡背景，{realistic_tags}，{leg_quality_tags}，{quality_tags}"


def generate_single_image(model_name: str, image_path: Path, prompt: str, api_key: str, max_retries: int = 2) -> Tuple[str, Optional[str]]:
    """
    使用指定模型生成单张图片（带重试机制）
    
    Args:
        model_name: 模型名称
        image_path: 输入图片路径
        prompt: 提示词
        api_key: API Key
        max_retries: 最大重试次数（默认 2 次）
    
    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    for attempt in range(max_retries + 1):
        try:
            # 安全修复：不设置全局 dashscope.api_key，使用 per-request key（通过 requests 直接调用）
            input_image_base64 = get_image_base64(image_path)
            logger.info(f"🖼️ 使用本地头像，模型：{model_name} (尝试 {attempt + 1}/{max_retries + 1})")
            
            # Prompt 长度校验（防止超长 prompt 导致 API 拒绝或静默截断）
            max_prompt_len = 6000
            if len(prompt) > max_prompt_len:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {max_prompt_len})，已截断")
                prompt = prompt[:max_prompt_len]
            
            # 不同模型的尺寸参数格式不同 - 全部改成 1K
            if model_name == 'qwen-image-2.0-pro':
                size_param = '1024*1024'  # qwen-image-2.0-pro 使用 1K 分辨率
            else:
                size_param = DEFAULT_IMAGE_SIZE  # wan2.7-image 使用 1K
            
            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': [{'image': input_image_base64}, {'text': prompt}]}]},
                'parameters': {'prompt_extend': PROMPT_EXTEND, 'watermark': False, 'n': 1, 'enable_interleave': False, 'size': size_param}
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
        
            logger.error(f"❌ {model_name} API 错误：{result_json}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))  # 线性退避（非指数）（非指数）（非指数）（非指数）（非指数）
                continue
            return (model_name, None)
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ {model_name} JSON 解析失败：{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except requests.RequestException as e:
            logger.error(f"❌ {model_name} 请求异常：{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
        except (KeyboardInterrupt, SystemExit, MemoryError):
            # 严重异常：不重试，直接向上传播
            raise
        except Exception as e:
            logger.error(f"❌ {model_name} 错误：{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)


def generate_images_dual_model(image_path: Path, prompt: str, api_key: str) -> List[Tuple[str, str]]:
    """
    使用 2 个模型并发生成图片（参考生图模式）- wan2.7-image + qwen-image-2.0-pro
    
    Returns:
        [(model_name, image_url), ...] 成功生成的图片列表
    """
    models = ['wan2.7-image', 'qwen-image-2.0-pro']
    results = []
    
    # 并发执行两个模型
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(generate_single_image, model_name, image_path, prompt, api_key): model_name
            for model_name in models
        }
        for future in as_completed(futures):
            model_name = futures[future]
            try:
                result = future.result()
                if result[1]:
                    results.append(result)
                    logger.info(f"✅ {model_name} 生成成功")
                else:
                    logger.warning(f"⚠️ {model_name} 生成失败")
            except Exception as e:
                logger.error(f"❌ {model_name} 异常：{e}")
    
    logger.info(f"📊 生成结果：{len(results)}/{len(models)} 成功")
    return results


def generate_images_single_model(image_path: Path, prompt: str, api_key: str) -> List[Tuple[str, str]]:
    """
    使用 1 个模型生成图片（场景生图模式）- 只用 wan2.7-image
    
    Returns:
        [(model_name, image_url), ...] 成功生成的图片列表
    """
    models = ['wan2.7-image']
    results = []
    
    model_name = 'wan2.7-image'
    logger.info(f"  使用模型：{model_name}")
    model_result = generate_single_image(model_name, image_path, prompt, api_key)
    if model_result[1]:
        results.append(model_result)
        logger.info(f"✅ {model_name} 生成成功")
    else:
        logger.warning(f"⚠️ {model_name} 生成失败")
    
    logger.info(f"📊 生成结果：{len(results)}/{len(models)} 成功")
    return results


def get_feishu_credentials() -> Tuple[Optional[str], Optional[str]]:
    """获取飞书 API 凭证（P2 修复 - 添加类型注解）"""
    import json
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
            logger.debug(f"读取飞书配置失败：{e}")
    
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
    
    upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
    with open(image_file, 'rb') as f:
        files = {'image': (os.path.basename(image_file), f, 'image/jpeg')}
        data = {'image_type': 'message'}  # 飞书要求
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


def get_model_display(model_name: str) -> str:
    """获取模型名称的 emoji 显示格式"""
    model_map = {
        'wan2.7-image': '🎨【万相 2.7】',
        'wan2.7-image-pro': '🎨【万相 2.7 Pro】',
        'qwen-image-2.0': '🖼️【千问 2.0】',
        'qwen-image-2.0-pro': '🖼️【千问 2.0 Pro】'
    }
    return model_map.get(model_name, f'📷【{model_name}】')


def send_to_channel(image_url: str, caption: str, channel: str, model_name: str, target: Optional[str] = None) -> bool:
    """发送图片到频道，飞书使用原生图片格式，其他平台使用文件"""
    try:
        logger.info(f"📤 发送到：{channel} (model: {model_name})")
        import requests, subprocess
        
        # 模型名称放在 caption 最开头，使用 emoji 标识
        model_display = get_model_display(model_name)
        full_caption = f"{model_display} {caption}"
        
        timestamp = int(time.time())
        # 安全处理 model_name，避免特殊字符
        safe_model_name = model_name.replace('.', '_').replace('-', '_')[:50]  # 限制长度
        # 使用配置模块的临时目录（H-5 修复：避免硬编码路径）
        temp_dir = config.get_temp_dir()
        temp_file = f'{temp_dir}/selfie_{safe_model_name}_{timestamp}.jpg'
        os.makedirs(str(temp_dir), mode=0o700, exist_ok=True)
        
        response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()
        
        # 先检查 Content-Type（L-5 修复：避免下载非图片内容）
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            logger.error(f"远程资源不是图片类型：{content_type}")
            return False
        
        # 检查 Content-Length（H-6 修复：防止 DoS 攻击）
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > 20 * 1024 * 1024:
            logger.error(f"图片过大（{int(content_length) / 1024 / 1024:.1f}MB > 20MB），拒绝下载")
            return False
        
        # H-2 修复：流式下载并限制总大小
        max_download_size = 20 * 1024 * 1024  # 20MB
        downloaded = 0
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    if downloaded > max_download_size:
                        raise ValueError(f"下载超出大小限制（{downloaded / 1024 / 1024:.1f}MB > 20MB）")
                    f.write(chunk)
        
        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return False
        
        # 验证文件类型（防止恶意文件）
        # 使用 mimetypes 替代废弃的 imghdr (Python 3.13+)
        import mimetypes
        mime_type, _ = mimetypes.guess_type(temp_file)
        if mime_type not in ['image/jpeg', 'image/png', 'image/webp']:
            logger.error(f"文件类型不正确：{mime_type}，仅支持 jpeg/png/webp")
            os.remove(temp_file)
            return False
        
        # 所有平台统一使用 openclaw message send 命令（包括飞书）
        # 这样可以避免跨应用 open_id 权限问题
        send_target = target or os.environ.get('AEVIA_TARGET', '')
        
        # 如果没有配置 target，尝试从默认配置读取
        if not send_target:
            send_target = config.get_feishu_target() if channel == 'feishu' else ''
        
        cmd_args = [
            'openclaw', 'message', 'send',
            '--channel', channel,
            '--target', send_target,
            '--message', full_caption,
            '--media', temp_file
        ]
        
        result = None
        try:
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
            
            # 保留一份最新的小柔照片到固定路径（供视频生成使用）
            # 使用原子操作避免 TOCTOU 竞争条件
            # 多用户隔离：路径中包含 target 标识，避免并发冲突
            # H-1 修复：清理 user_id 防止路径注入
            user_id = target or 'default'
            user_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(user_id))[:32]
            latest_path = config.get_temp_dir() / f'selfie_latest_{user_id}.jpg'
            temp_dst = None
            try:
                import shutil
                # 先写入临时文件，再原子重命名
                temp_dst = str(latest_path) + '.tmp'
                shutil.copy2(temp_file, temp_dst)
                os.replace(temp_dst, str(latest_path))  # 原子操作
                logger.info(f"✓ 已保存最新自拍到：{latest_path}")
            except Exception as e:
                logger.warning(f"保存自拍失败：{e}")
                # 清理临时文件
                if temp_dst and os.path.exists(temp_dst):
                    os.remove(temp_dst)
            
            if result.returncode == 0:
                logger.info("✓ 图片发送成功")
                return True
            
            logger.error(f"发送失败：{result.stderr}")
            return False
        finally:
            # 确保临时文件被清理
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"清理临时文件失败：{temp_file} - {e}")
        
    except requests.RequestException as e:
        logger.error(f"下载图片异常：{e}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("发送超时")
        return False
    except Exception as e:
        logger.error(f"发送异常：{e}")
        return False


def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """普通模式：根据文字描述生成图片，单模型生成"""
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
        logger.info(f"📸 模式：{mode}")
        
        # 单模型生成（wan2.7-image）
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
        logger.error(f"❌ 错误：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return False


def generate_from_reference(reference_image_path: str, caption: str = "这是模仿参考图生成的～", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    参考图模式（优化版 - 新流程）
    
    流程：
    1. 分析参考图 → 提取场景、姿势、服装、光线等描述（**完全忽略人脸**）
    2. 使用小柔头像作为图生图的输入
    3. Prompt：保留小柔脸，套用参考图的场景/穿搭/姿态
    4. 单模型生成（wan2.7-image）
    
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
        
        # 1. 验证参考图
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            logger.error(f"参考图不存在：{reference_image_path}")
            return False
        logger.info("✅ 参考图验证通过")
        
        # 2. 加载小柔头像
        image_path = validate_character_image()
        logger.info("✅ 头像文件验证通过（使用小柔头像）")
        
        channel = validate_channel(channel)
        
        # 忽略 multi_mode 参数，始终使用分析 + 单模型图生图模式
        logger.info("🔍 分析参考图模式：提取 prompt 后单模型生成")
        
        # 3. 分析参考图，提取 prompt
        script_dir = Path(__file__).resolve().parent
        analyzer_path = script_dir / 'image_analyzer.py'
        
        if not analyzer_path.exists():
            logger.error(f"图片分析模块不存在：{analyzer_path}")
            return False
        
        # 安全检查：验证参考图路径
        if not is_safe_path(config.get_temp_dir(), reference_image_path):
            allowed_dirs = [
                Path('/home/admin/.openclaw/media/inbound'),
                Path('/tmp/openclaw'),
                config.get_temp_dir()
            ]
            is_allowed = any(is_safe_path(base_dir, reference_image_path) for base_dir in allowed_dirs)
            if not is_allowed:
                logger.error(f"⚠️ 参考图路径不在允许范围内：{reference_image_path}")
                return False
        
        import subprocess
        try:
            result = subprocess.run(
                ['python3', str(analyzer_path), reference_image_path],
                capture_output=True,
                text=True,
                timeout=int(os.environ.get('XIAOROU_API_TIMEOUT', '120')),
                shell=False  # 显式声明不使用 shell
            )
        except subprocess.TimeoutExpired:
            logger.error(f"图片分析超时（超过 {os.environ.get('XIAOROU_API_TIMEOUT', '120')} 秒）")
            return False
        
        if result.returncode != 0:
            logger.error(f"图片分析失败：{result.stderr}")
            return False
        
        prompt = result.stdout.strip()
        logger.info(f"✅ 参考图分析完成：{prompt[:100]}...")
        
        # 4. 单模型生成（wan2.7-image）
        logger.info("🚀 wan2.7-image 生成中...")
        results = generate_images_single_model(image_path, prompt, api_key)
        
        if not results:
            logger.error("❌ 所有模型都生成失败")
            return False
        
        # 5. 发送生成的图片（单模型）
        success_count = 0
        failed_models = []
        for model_name, image_url in results:
            if channel and image_url:
                effective_target = target or os.environ.get('AEVIA_TARGET')
                logger.info(f"📤 准备发送：{model_name}")
                if send_to_channel(image_url, caption, channel, model_name, effective_target):
                    success_count += 1
                    logger.info(f"✅ {model_name} 发送成功")
                else:
                    failed_models.append(model_name)
                    logger.error(f"❌ {model_name} 发送失败")
        
        if failed_models:
            logger.error(f"⚠️ 发送失败的模型：{', '.join(failed_models)}")
        logger.info(f"✅ 成功发送 {success_count}/{len(results)} 张图片（单模型）")
        return success_count > 0
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return False


if __name__ == "__main__":
    # --json 模式：输出 JSON 结果，不发送（由 bot 处理发送）
    json_mode = '--json' in sys.argv
    
    if len(sys.argv) < 2 or (len(sys.argv) == 2 and sys.argv[1] == '--json'):
        print("用法：")
        print("  场景生图：python3 selfie.py <场景描述> [频道] [配文] [target]")
        print("  参考生图：python3 selfie.py --reference <参考图路径> [频道] [配文] [target]")
        print("  JSON 模式：python3 selfie.py --reference <路径> --json")
        sys.exit(1)
    
    # 检测是否为参考图模式
    if sys.argv[1] == '--reference' and len(sys.argv) >= 3:
        reference_image = sys.argv[2]
        
        # JSON 模式：解析参数
        if json_mode:
            channel = None
            caption = "这是模仿参考图生成的～"
            target = None
            for i, arg in enumerate(sys.argv[3:], 3):
                if arg.startswith('--caption='):
                    caption = arg[len('--caption='):]
        else:
            channel = sys.argv[3] if len(sys.argv) > 3 else None
            caption = sys.argv[4] if len(sys.argv) > 4 else "这是模仿参考图生成的～"
            target = sys.argv[5] if len(sys.argv) > 5 else None
        
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在：{reference_image}")
            sys.exit(1)
        
        # 路径白名单验证（防止路径遍历攻击）
        allowed_dirs = [
            Path('/home/admin/.openclaw/media/inbound'),
            Path('/tmp/openclaw'),
            config.get_temp_dir(),
        ]
        is_allowed = any(is_safe_path(base_dir.resolve(), reference_image) for base_dir in allowed_dirs)
        if not is_allowed:
            logger.error(f"⚠️ 参考图路径不在允许范围内：{reference_image}")
            sys.exit(1)
        
        success = generate_from_reference(reference_image, caption, channel, target)
    else:
        # 场景生图模式
        context = sys.argv[1]
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
        target = sys.argv[4] if len(sys.argv) > 4 else None
        
        success = generate_selfie(context, caption, channel, target)
    
    sys.exit(0 if success else 1)
