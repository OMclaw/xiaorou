#!/usr/bin/env python3
"""selfie.py - 自拍生成模块 (双模型并发)

支持两种模式：
1. 普通模式：根据文字描述生成
2. 参考图模式：直接使用参考图进行图生图（不分析）

每次生成使用两个模型各生成一张：
- wan2.6-image
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
    
    # 真实感增强标签 - 自然光滑，无黑点，淡粉色嘴唇，无腮红
    realistic_tags = "真实摄影，自然光滑皮肤，清透肌肤，真实光影，柔和光线，生活照风格，无 AI 感，无塑料感，无黑点，无瑕疵，自然唇色，淡粉色嘴唇，无腮红，清淡底妆"
    
    # 质量标签
    quality_tags = "8K 超高清，电影级布光，细节丰富，色彩自然"
    
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        return "mirror", f"{influencer_style}，{context}，全身照，对镜拍摄，网红打卡场景，自然光线，{realistic_tags}，{quality_tags}"
    
    # 默认网红风格 prompt - 强调自然真实
    return "direct", f"{influencer_style}，{context}，眼神直视镜头，自然微笑，真实五官，时尚造型，网红打卡背景，{realistic_tags}，{quality_tags}"


def generate_images_single_model(image_path: Path, prompt: str, api_key: str) -> Optional[str]:
    """
    使用 qwen-image-2.0-pro 模型生成单张图片（单图输入）
    
    Returns:
        image_url 或 None 如果失败
    """
    try:
        dashscope.api_key = api_key
        input_image_base64 = get_image_base64(image_path)
        logger.info(f"🖼️ 使用本地头像，模型：qwen-image-2.0-pro")
        
        # qwen-image-2.0-pro 需要 width*height 格式
        size_param = '1024*1024'
        
        payload = {
            'model': 'qwen-image-2.0-pro',
            'input': {'messages': [{'role': 'user', 'content': [{'image': input_image_base64}, {'text': prompt}]}]},
            'parameters': {'prompt_extend': PROMPT_EXTEND, 'watermark': False, 'n': 1, 'enable_interleave': False, 'size': size_param}
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
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info("✅ qwen-image-2.0-pro 生成成功")
                return image_url
        
        logger.error(f"❌ API 错误：{result_json}")
        return None
        
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


def generate_images_multi_model(image_path: Path, reference_image_path: Path, prompt: str, api_key: str) -> Optional[str]:
    """
    使用 qwen-image-2.0-pro 模型生成单张图片（多图融合输入）
    
    Args:
        image_path: 小柔头像路径
        reference_image_path: 参考图路径
        prompt: 融合指令 prompt
    
    Returns:
        image_url 或 None 如果失败
    """
    try:
        dashscope.api_key = api_key
        input_image_base64 = get_image_base64(image_path)
        ref_image_base64 = get_image_base64(reference_image_path)
        logger.info(f"🖼️ 多图融合模式：小柔头像 + 参考图，模型：qwen-image-2.0-pro")
        
        # qwen-image-2.0-pro 需要 width*height 格式
        size_param = '1024*1024'
        
        # 多图输入：先传小柔头像，再传参考图，最后是文本指令
        payload = {
            'model': 'qwen-image-2.0-pro',
            'input': {'messages': [{'role': 'user', 'content': [
                {'image': input_image_base64},  # 图 1：小柔头像
                {'image': ref_image_base64},    # 图 2：参考图
                {'text': prompt}                 # 融合指令
            ]}]},
            'parameters': {'prompt_extend': False, 'watermark': False, 'n': 1, 'enable_interleave': False, 'size': size_param}
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
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info("✅ qwen-image-2.0-pro 多图融合成功")
                return image_url
        
        logger.error(f"❌ API 错误：{result_json}")
        return None
        
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


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


def get_model_display() -> str:
    """获取模型名称的 emoji 显示格式"""
    return '🖼️【万相 2.0 Pro】'


def send_to_channel(image_url: str, caption: str, channel: str, target: Optional[str] = None) -> bool:
    """发送图片到频道，飞书使用原生图片格式，其他平台使用文件"""
    try:
        logger.info(f"📤 发送到：{channel}")
        import requests, subprocess
        
        # 模型名称放在 caption 最开头，使用 emoji 标识
        model_display = get_model_display()
        full_caption = f"{model_display} {caption}"
        
        timestamp = int(time.time())
        temp_file = f'/tmp/openclaw/selfie_{timestamp}.jpg'
        os.makedirs('/tmp/openclaw', exist_ok=True)
        
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return False
        
        if channel == "feishu":
            send_target = target or os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')
            receive_id = send_target.replace('user:', '') if send_target.startswith('user:') else send_target
            
            image_key = upload_feishu_image(temp_file)
            if image_key:
                success = send_feishu_image_message(image_key, full_caption, receive_id, "open_id")
                os.remove(temp_file)
                return success
        
        send_target = target or os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')
        
        cmd_args = [
            'openclaw', 'message', 'send',
            '--channel', channel,
            '--target', send_target,
            '--message', full_caption,
            '--media', temp_file
        ]
        
        result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
        
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
        
        # 使用 qwen-image-2.0-pro 生成
        logger.info("🚀 正在生成图片...")
        image_url = generate_images_single_model(image_path, prompt, api_key)
        
        if not image_url:
            logger.error("❌ 生成失败")
            return False
        
        # 发送图片
        if channel and image_url:
            if not target:
                target = os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, target):
                success_count += 1
        
        logger.info(f"✅ 成功发送 {success_count}/{len(results)} 张图片")
        return success_count > 0
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return False


def generate_from_reference(reference_image_path: str, caption: str = "这是模仿参考图生成的～", channel: Optional[str] = None, target: Optional[str] = None, multi_mode: bool = False) -> bool:
    """
    参考图模式：分析参考图后，使用小柔头像进行图生图
    
    工作流程：
    方案一（multi_mode=False）：
    1. 分析参考图 → 提取场景、姿势、服装、光线等描述
    2. 使用小柔头像作为图生图的输入
    3. Prompt 强调保持小柔脸部特征一致性
    4. 生成图片
    
    方案二（multi_mode=True）：
    1. 小柔头像 + 参考图直接传给模型
    2. 多图融合生成
    
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
            # ===== 方案二：多图融合模式 =====
            logger.info("🔀 多图融合模式：小柔头像 + 参考图直接融合")
            
            # 多图融合 prompt
            fusion_prompt = """这是一张人物肖像融合创作。
图 1 是小柔的头像，请保持她的脸部特征：五官、脸型、发型、妆容风格。
图 2 是参考图，请学习参考图的场景、姿势、服装、光线、氛围。

要求：
1. 必须严格保持图 1 人物的脸部特征一致性，不要改变她的眼睛、鼻子、嘴巴、眉毛形状
2. 采用图 2 的场景、姿势、服装、光线
3. 保持图 1 人物的身份特征，确保是小柔本人
4. 妆容清淡自然，裸妆效果，无腮红，自然唇色，淡粉色嘴唇
5. 真实摄影风格，自然光滑皮肤，清透肌肤，无 AI 感，无塑料感

将图 1 的人物完美融入图 2 的场景中，保持脸部一致性的同时，学习参考图的整体风格和氛围。"""
            
            logger.info("🚀 正在生成图片（多图融合）...")
            image_url = generate_images_multi_model(image_path, ref_path, fusion_prompt, api_key)
            
        else:
            # ===== 方案一：分析 + 图生图模式 =====
            logger.info("🔍 分析参考图模式：提取 prompt 后图生图")
            
            # 3. 分析参考图，提取 prompt
            script_dir = Path(__file__).resolve().parent
            analyzer_path = script_dir / 'image_analyzer.py'
            
            if not analyzer_path.exists():
                logger.error(f"图片分析模块不存在：{analyzer_path}")
                return False
            
            import subprocess
            result = subprocess.run(
                ['python3.11', str(analyzer_path), reference_image_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"图片分析失败：{result.stderr}")
                return False
            
            prompt = result.stdout.strip()
            logger.info(f"✅ 参考图分析完成：{prompt[:100]}...")
            
            # 4. 使用 qwen-image-2.0-pro 生成（使用小柔头像）
            logger.info("🚀 正在生成图片...")
            image_url = generate_images_single_model(image_path, prompt, api_key)
        
        if not image_url:
            logger.error("❌ 生成失败")
            return False
        
        # 5. 发送图片
        success_count = 0
        if channel and image_url:
            if not target:
                target = os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, target):
                success_count += 1
        
        logger.info(f"✅ 成功发送 {success_count} 张图片")
        return success_count > 0
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 selfie.py <场景描述 | --reference 参考图路径> [--multi] [频道] [配文] [target]")
        sys.exit(1)
    
    # 检测是否为参考图模式
    if sys.argv[1] == '--reference' and len(sys.argv) >= 3:
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
