#!/usr/bin/env python3
"""selfie.py - 自拍生成模块 (双模型并发)

支持两种模式：
1. 普通模式：根据文字描述生成
2. 参考图模式：直接使用参考图进行图生图（不分析）

每次生成使用两个模型各生成一张：
- wan2.7-image
- qwen-image-2.0-pro
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
PROMPT_EXTEND = False

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception): pass
class FileNotFoundError(Exception): pass


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
    净化用户输入，移除危险字符
    
    Args:
        text: 原始输入文本
        max_length: 最大长度
    
    Returns:
        净化后的文本
    """
    if not text: return ""
    if len(text) > max_length:
        logger.warning(f"输入过长，已截断至 {max_length}")
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
    """验证并加载 API Key，支持环境变量和 OpenClaw 配置文件"""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
        logger.info("✓ 从环境变量加载 API Key")
        return api_key
    
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
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
    """构建网红风格图片生成 prompt - 自然真实版本"""
    context_lower = context.lower()
    
    # 网红风格基础元素 - 减少 AI 感，增加真实感，清淡妆容，无腮红
    influencer_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，无腮红"
    
    # 真实感增强标签 - 自然光滑，无黑点，淡粉色嘴唇，无腮红，色彩自然，正确人体结构，清淡妆容
    realistic_tags = "真实摄影，自然光滑皮肤，清透肌肤，真实光影，柔和光线，生活照风格，无 AI 感，无塑料感，无黑点，无瑕疵，无口红，裸唇，唇色自然，无妆感，嘴唇本色，无腮红，清淡底妆，底妆轻薄透明，腮红极淡，几乎无腮红，裸妆效果，妆容极淡，色彩柔和自然，低饱和度，避免过度鲜艳，正确人体结构，正常双手，无多余肢体，妆容清淡自然，脸部妆容自然，避免浓妆，色彩素雅，莫兰迪色系，极低饱和度，色彩非常淡，淡雅色调，低对比度，柔和色彩"
    
    # 质量标签 - 强调色彩自然和正确结构
    quality_tags = "8K 超高清，电影级布光，细节丰富，色彩自然柔和，低饱和度，真实色调，正确人体比例，妆容自然，素雅色彩，极低饱和度"
    
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"{influencer_style}，{context}，全身照，对镜拍摄，网红打卡场景，自然光线，{realistic_tags}，{quality_tags}"
    
    # 默认网红风格 prompt - 强调自然真实
    return "direct", f"{influencer_style}，{context}，眼神直视镜头，自然微笑，真实五官，时尚造型，网红打卡背景，{realistic_tags}，{quality_tags}"


def generate_single_image(model_name: str, image_path: Path, prompt: str, api_key: str, extra_images: Optional[List[Path]] = None) -> Tuple[str, Optional[str]]:
    """
    使用指定模型生成单张图片
    
    Args:
        extra_images: 额外参考图片列表（多图模式，提升脸部一致性）
    
    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    try:
        dashscope.api_key = api_key
        input_image_base64 = get_image_base64(image_path)
        logger.info(f"🖼️ 使用本地头像，模型：{model_name}")
        
        # 不同模型的尺寸参数格式不同 - 全部改成 1K
        if model_name == 'qwen-image-2.0-pro':
            size_param = '1024*1024'  # qwen-image-2.0-pro 使用 1K 分辨率
        else:
            size_param = DEFAULT_IMAGE_SIZE  # wan2.7-image 使用 1K
        
        # 构建 content 数组：支持多张参考图片
        content_items = [{'image': input_image_base64}]
        if extra_images:
            for extra_img in extra_images:
                if extra_img.exists():
                    content_items.append({'image': get_image_base64(extra_img)})
                    logger.info(f"📎 添加额外参考图：{extra_img.name}")
        content_items.append({'text': prompt})
        
        payload = {
            'model': model_name,
            'input': {'messages': [{'role': 'user', 'content': content_items}]},
            'parameters': {
                'prompt_extend': PROMPT_EXTEND,
                'watermark': False,
                'n': 1,
                'enable_interleave': False,
                'size': size_param,
                'seed': 42,
                'negative_prompt': get_negative_prompt(),
            }
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}'
            },
            json=payload, timeout=120
        )
        
        result_json = response.json()
        if response.status_code == 200 and result_json.get('output'):
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info(f"✅ {model_name} 生成成功")
                return (model_name, image_url)
        
        logger.error(f"❌ {model_name} API 错误：{result_json}")
        return (model_name, None)
        
    except Exception as e:
        logger.error(f"❌ {model_name} 错误：{e}")
        return (model_name, None)


def generate_images_dual_model(image_path: Path, prompt: str, api_key: str, model_prompts: Optional[dict] = None, extra_images: Optional[List[Path]] = None) -> List[Tuple[str, str]]:
    """
    使用两个模型并发生成图片
    
    Args:
        model_prompts: 可选，按模型指定 prompt {model_name: prompt}
        extra_images: 额外参考图片列表（多图模式）
    
    Returns:
        [(model_name, image_url), ...] 成功生成的图片列表
    """
    models = ['wan2.7-image', 'qwen-image-2.0-pro']
    results = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        for model in models:
            model_prompt = model_prompts.get(model, prompt) if model_prompts else prompt
            futures[executor.submit(generate_single_image, model, image_path, model_prompt, api_key, extra_images=extra_images)] = model
        
        for future in as_completed(futures):
            model_name, image_url = future.result()
            if image_url:
                results.append((model_name, image_url))
    
    return results


def get_feishu_credentials():
    """获取飞书 API 凭证"""
    import json
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            app_id = config.get('channels', {}).get('feishu', {}).get('appId', '')
            app_secret = config.get('channels', {}).get('feishu', {}).get('appSecret', '')
            
            if not app_id or not app_secret:
                default_account = config.get('channels', {}).get('feishu', {}).get('defaultAccount', 'main')
                accounts = config.get('channels', {}).get('feishu', {}).get('accounts', {})
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
        'qwen-image-2.0-pro': '🖼️【千问 2.0 Pro】'
    }
    return model_map.get(model_name, f'📷【{model_name}】')


def save_image_locally(image_url: str, model_name: str) -> Optional[str]:
    """
    下载图片到本地临时目录，返回文件路径。
    不再使用 subprocess 调用 openclaw message send（子进程缺少 gateway 会话上下文）。
    由上层 agent 读取 stdout 的 JSON 输出后，用 agent 自己的 message 工具发送。
    
    Returns:
        文件路径，失败返回 None
    """
    try:
        import mimetypes
        import shutil
        
        os.makedirs('/tmp/openclaw', exist_ok=True)
        timestamp = int(time.time())
        temp_file = f'/tmp/openclaw/selfie_{model_name}_{timestamp}.jpg'
        
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return None
        
        mime_type, _ = mimetypes.guess_type(temp_file)
        if mime_type not in ['image/jpeg', 'image/png', 'image/webp']:
            logger.error(f"文件类型不正确：{mime_type}，仅支持 jpeg/png/webp")
            os.remove(temp_file)
            return None
        
        # 保留一份最新的小柔照片到固定路径（供视频生成使用）
        latest_path = config.get_temp_dir() / 'selfie_latest.jpg'
        temp_dst = None
        try:
            temp_dst = str(latest_path) + '.tmp'
            shutil.copy2(temp_file, temp_dst)
            os.replace(temp_dst, str(latest_path))
            logger.info(f"✓ 已保存最新自拍到：{latest_path}")
        except Exception as e:
            logger.warning(f"保存最新自拍失败：{e}")
            if temp_dst and os.path.exists(temp_dst):
                os.remove(temp_dst)
        
        logger.info(f"✓ 图片已下载到本地：{temp_file}")
        return temp_file
        
    except requests.RequestException as e:
        logger.error(f"下载图片异常：{e}")
        return None
    except Exception as e:
        logger.error(f"保存图片异常：{e}")
        return None


def output_json_result(result_type: str, data: dict):
    """输出 JSON 结果到 stdout，供上层 agent 解析"""
    output = {"type": result_type, **data}
    print(json.dumps(output, ensure_ascii=False), flush=True)


def send_to_channel(image_url: str, caption: str, channel: str, model_name: str, target: Optional[str] = None) -> Optional[dict]:
    """
    保存图片到本地，返回结果字典（不再调用 openclaw CLI）。
    
    Returns:
        {'file_path': str, 'caption': str, 'model_name': str, 'channel': str} 或 None
    """
    logger.info(f"📤 保存图片到本地：{channel} (model: {model_name})")
    
    model_display = get_model_display(model_name)
    full_caption = f"{model_display} {caption}"
    
    file_path = save_image_locally(image_url, model_name)
    if not file_path:
        return None
    
    result = {
        'file_path': file_path,
        'caption': full_caption,
        'model_name': model_name,
        'channel': channel,
        'target': target or os.environ.get('AEVIA_TARGET', ''),
    }
    
    # 输出 JSON 到 stdout，供上层 agent 读取并发送
    output_json_result('image_ready', {
        'file': file_path,
        'caption': full_caption,
    })
    
    return result


def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """普通模式：根据文字描述生成图片，双模型并发"""
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
        
        # 双模型并发生成
        logger.info("🚀 双模型并发生成中...")
        results = generate_images_dual_model(image_path, prompt, api_key)
        
        if not results:
            logger.error("❌ 两个模型都生成失败")
            output_json_result('error', {'message': '两个模型都生成失败'})
            return False
        
        # 保存所有成功生成的图片
        image_results = []
        for model_name, image_url in results:
            if channel and image_url:
                if not target:
                    target = os.environ.get('AEVIA_TARGET')
                result = send_to_channel(image_url, caption, channel, model_name, target)
                if result:
                    image_results.append(result)
        
        if image_results:
            output_json_result('done', {
                'success': True,
                'count': len(image_results),
                'images': [{'file': r['file_path'], 'caption': r['caption']} for r in image_results],
            })
            logger.info(f"✅ 成功保存 {len(image_results)}/{len(results)} 张图片")
            return True
        
        logger.error("❌ 保存图片全部失败")
        return False
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False


def generate_from_reference(reference_image_path: str, caption: str = "这是模仿参考图生成的～", channel: Optional[str] = None, target: Optional[str] = None, multi_mode: bool = False) -> bool:
    """
    参考图模式（优化版 - 新流程）
    
    流程：
    1. 分析参考图 → 提取场景、姿势、服装、光线等描述（**完全忽略人脸**）
    2. 使用小柔头像作为图生图的输入
    3. Prompt：保留小柔脸，套用参考图的场景/穿搭/姿态
    4. 双模型并发生成（wan2.7-image + qwen-image-2.0-pro）
    
    Args:
        reference_image_path: 参考图路径
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标
        multi_mode: 是否使用多图融合模式
    
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
        
        if multi_mode:
            # ===== 多图融合模式 =====
            logger.info("🔀 多图融合模式：小柔头像 + 参考图直接融合")
            
            fusion_prompt = """【人物一致性融合创作】
图 1 是小柔头像，必须严格保持她的脸部特征完全不变。
图 2 是参考图，只学习场景、姿势、服装、光线、氛围。
妆容清淡自然，裸妆效果，无腮红。真实摄影风格。"""
            
            logger.info("🚀 正在生成图片（多图融合）...")
            image_url = generate_images_multi_model(image_path, ref_path, fusion_prompt, api_key)
            
            if not image_url:
                logger.error("❌ 生成失败")
                output_json_result('error', {'message': '多图融合生成失败'})
                return False
            
            if not target:
                target = os.environ.get('AEVIA_TARGET')
            result = send_to_channel(image_url, caption, channel, "qwen-image-2.0-pro", target)
            
            if result:
                output_json_result('done', {
                    'success': True, 'count': 1,
                    'images': [{'file': result['file_path'], 'caption': result['caption']}],
                })
                return True
            
            logger.error("❌ 保存图片失败")
            return False
            
        else:
            # ===== 分析 + 图生图模式（双模型并发） =====
            logger.info("🔍 分析参考图模式：提取 prompt 后双模型并发生成")
            
            script_dir = Path(__file__).resolve().parent
            analyzer_path = script_dir / 'image_analyzer.py'
            
            if not analyzer_path.exists():
                logger.error(f"图片分析模块不存在：{analyzer_path}")
                return False
            
            # 导入 analyzer 模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("image_analyzer", analyzer_path)
            analyzer_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(analyzer_module)
            
            # 分别生成英文和中文 prompt
            description_en = analyzer_module.analyze_image(reference_image_path, api_key, language='en')
            prompt_en = analyzer_module.build_reference_prompt(description_en, language='en')
            description_zh = analyzer_module.analyze_image(reference_image_path, api_key, language='zh')
            prompt_zh = analyzer_module.build_reference_prompt(description_zh, language='zh')
            
            logger.info(f"✅ 参考图分析完成")
            
            # 双模型并发生成
            logger.info("🚀 双模型并发生成中...")
            model_prompts = {
                'wan2.7-image': prompt_en,
                'qwen-image-2.0-pro': prompt_zh,
            }
            results = generate_images_dual_model(image_path, '', api_key, model_prompts=model_prompts)
            
            if not results:
                logger.error("❌ 两个模型都生成失败")
                output_json_result('error', {'message': '两个模型都生成失败'})
                return False
            
            # 保存所有成功生成的图片
            image_results = []
            for model_name, image_url in results:
                if channel and image_url:
                    if not target:
                        target = os.environ.get('AEVIA_TARGET')
                    result = send_to_channel(image_url, caption, channel, model_name, target)
                    if result:
                        image_results.append(result)
            
            if image_results:
                output_json_result('done', {
                    'success': True, 'count': len(image_results),
                    'images': [{'file': r['file_path'], 'caption': r['caption']} for r in image_results],
                })
                logger.info(f"✅ 成功保存 {len(image_results)}/{len(results)} 张图片")
                return True
            
            logger.error("❌ 保存图片全部失败")
            return False
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False


def generate_single_image_for_face_swap(model_name: str, target_image_path: Path, face_reference_path: Path, prompt: str, api_key: str) -> Tuple[str, Optional[str]]:
    """
    换脸模式专用：以目标图为主输入，小柔头像为脸部分参考
    """
    try:
        dashscope.api_key = api_key
        target_base64 = get_image_base64(target_image_path)
        face_base64 = get_image_base64(face_reference_path)
        logger.info(f"🖼️ 换脸模式 - 主输入：{target_image_path.name}，脸部参考：{face_reference_path.name}，模型：{model_name}")
        
        if model_name == 'qwen-image-2.0-pro':
            size_param = '1024*1024'
        else:
            size_param = DEFAULT_IMAGE_SIZE
        
        content_items = [
            {'image': target_base64},
            {'image': face_base64},
            {'text': prompt}
        ]
        
        payload = {
            'model': model_name,
            'input': {'messages': [{'role': 'user', 'content': content_items}]},
            'parameters': {
                'prompt_extend': PROMPT_EXTEND,
                'watermark': False,
                'n': 1,
                'enable_interleave': False,
                'size': size_param,
                'seed': 42,
                'negative_prompt': get_negative_prompt(),
            }
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}'
            },
            json=payload, timeout=180
        )
        
        result_json = response.json()
        if response.status_code == 200 and result_json.get('output'):
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info(f"✅ {model_name} 换脸生成成功")
                return (model_name, image_url)
        
        logger.error(f"❌ {model_name} API 错误：{result_json}")
        return (model_name, None)
        
    except Exception as e:
        logger.error(f"❌ {model_name} 换脸错误：{e}")
        return (model_name, None)


def get_negative_prompt() -> str:
    """返回 negative_prompt，明确告诉模型不要改变脸部特征"""
    return ("变形的人脸, 不同的五官, 不同的眼睛, 不同的鼻子, 不同的嘴巴, 不同的眉毛, "
            "不同的脸型, 脸型和参考图不一致, 身份不一致, 变成了其他人, 脸部扭曲, 五官位移, "
            "脸型和输入图片不一致, 换了另外一个人, 面部特征被改变, "
            "deformed face, different facial features, identity mismatch, morphed face, "
            "changed person, face distortion, inconsistent face shape, warped features")


def generate_face_swap(target_image_path: str, caption: str = "换脸完成～看看效果怎么样？", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    换脸模式：把小柔的脸换到用户照片的场景中，其他一切不变
    
    🎯 双图参考策略：
    - 用户照片 → 主输入图（场景/穿搭/姿势/光影 100% 来自它）
    - 小柔头像 → 额外参考图（提供脸部身份特征）
    """
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")
        
        target_path = Path(target_image_path)
        allowed_dirs = [
            Path('/home/admin/.openclaw/media/inbound'),
            Path('/tmp/openclaw'),
            config.get_temp_dir()
        ]
        
        is_allowed = any(is_safe_path(base_dir, target_image_path) for base_dir in allowed_dirs)
        if not is_allowed:
            logger.error(f"⚠️ 文件路径不在允许的范围内：{target_image_path}")
            return False
        
        if not target_path.exists():
            logger.error(f"目标图不存在：{target_image_path}")
            return False
        
        logger.info("✅ 目标图验证通过")
        
        face_ref_path = validate_character_image()
        logger.info("✅ 头像文件验证通过（使用小柔头像作为脸部参考）")
        
        channel = validate_channel(channel)
        
        # 分析目标图场景描述
        script_dir = Path(__file__).resolve().parent
        analyzer_path = script_dir / 'image_analyzer.py'
        
        if not analyzer_path.exists():
            logger.error(f"图片分析模块不存在：{analyzer_path}")
            return False
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("image_analyzer", analyzer_path)
        analyzer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analyzer_module)
        
        try:
            scene_description = analyzer_module.analyze_image_for_face_swap(str(target_path), api_key)
            logger.info(f"✅ 目标图场景分析完成：{scene_description[:100]}...")
        except Exception as e:
            logger.error(f"图片分析失败：{e}")
            return False
        
        # 构建换脸专用 prompt
        prompt_face_swap = f"""【核心指令：只换脸，其他完全保留】

这是一张人脸替换创作。请严格遵循以下规则：

1. 场景环境：完全保留目标图的场景、背景、建筑、装饰
2. 人物穿搭：完全保留目标图的服装款式、颜色、材质、配饰
3. 人物姿态：完全保留目标图的站姿/坐姿/手部动作/身体角度
4. 光线光影：完全保留目标图的光线方向、色调、明暗氛围
5. 拍摄构图：完全保留目标图的拍摄角度、景深、构图方式

唯一改变的是：把人物的脸替换为小柔的脸。

小柔的脸部特征：脸型为柔和的鹅蛋脸，杏仁形深棕色眼睛自然双眼皮，小巧挺拔的鼻子，唇形自然饱满淡粉色温柔微笑，自然弧度柔和眉毛，细腻光滑白皙肌肤，黑色长直发。

目标场景参考：{scene_description}

要求：换脸后脸部与原图光影自然融合，无违和感。清淡妆容，裸妆效果，无腮红。真实摄影风格，8K 超高清。"""
        
        # 双模型并发生成
        models = ['wan2.7-image', 'qwen-image-2.0-pro']
        results = []
        
        logger.info("🎯 换脸模式生成中（双图参考：目标图 + 小柔头像）...")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for model_name in models:
                future = executor.submit(
                    generate_single_image_for_face_swap,
                    model_name, target_path, face_ref_path, prompt_face_swap, api_key
                )
                futures[future] = model_name
            
            for future in as_completed(futures):
                model_name, image_url = future.result()
                if image_url:
                    results.append(('face_swap', model_name, image_url))
                    logger.info(f"✅ {model_name} 换脸成功")
        
        if not results:
            logger.error("❌ 所有换脸生成均失败")
            output_json_result('error', {'message': '所有换脸生成均失败'})
            return False
        
        # 保存所有成功生成的图片
        image_results = []
        for scheme, model_name, image_url in results:
            if channel and image_url:
                if not target:
                    target = os.environ.get('AEVIA_TARGET')
                scheme_caption = "换好了～你看看喜欢吗 💕"
                result = send_to_channel(image_url, scheme_caption, channel, model_name, target)
                if result:
                    image_results.append(result)
        
        if image_results:
            output_json_result('done', {
                'success': True, 'count': len(image_results),
                'images': [{'file': r['file_path'], 'caption': r['caption']} for r in image_results],
            })
            logger.info(f"✅ 成功保存 {len(image_results)}/{len(results)} 张换脸图片")
            return True
        
        logger.error("❌ 保存图片全部失败")
        return False
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        output_json_result('error', {'message': str(e)})
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  普通模式：python3 selfie.py <场景描述> [频道] [配文] [target]")
        print("  参考图模式：python3 selfie.py --reference <参考图路径> [--multi] [频道] [配文] [target]")
        print("  换脸模式：python3 selfie.py --face-swap <目标图路径> [频道] [配文] [target]")
        sys.exit(1)
    
    # 检测是否为换脸模式
    if sys.argv[1] == '--face-swap' and len(sys.argv) >= 3:
        target_image = sys.argv[2]
        channel = sys.argv[3] if len(sys.argv) > 3 else None
        caption = sys.argv[4] if len(sys.argv) > 4 else "换脸完成～看看效果怎么样？"
        target = sys.argv[5] if len(sys.argv) > 5 else None
        
        if not os.path.exists(target_image):
            logger.error(f"目标图不存在：{target_image}")
            sys.exit(1)
        
        success = generate_face_swap(target_image, caption, channel, target)
    
    # 检测是否为参考图模式
    elif sys.argv[1] == '--reference' and len(sys.argv) >= 3:
        # 参考图模式
        reference_image = sys.argv[2]
        
        # 检测是否启用多图融合模式
        multi_mode = False
        offset = 0
        if len(sys.argv) > 3 and sys.argv[3] == '--multi':
            multi_mode = True
            offset = 1
        
        channel = sys.argv[3 + offset] if len(sys.argv) > 3 + offset else None
        caption = sys.argv[4 + offset] if len(sys.argv) > 4 + offset else "这是模仿参考图生成的～"
        target = sys.argv[5 + offset] if len(sys.argv) > 5 + offset else None
        
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在：{reference_image}")
            sys.exit(1)
        
        success = generate_from_reference(reference_image, caption, channel, target, multi_mode)
    else:
        # 普通模式
        context = sys.argv[1]
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
        target = sys.argv[4] if len(sys.argv) > 4 else None
        
        success = generate_selfie(context, caption, channel, target)
    
    sys.exit(0 if success else 1)
