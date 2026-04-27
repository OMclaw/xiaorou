#!/usr/bin/env python3.11
"""selfie_inpaint.py - 小柔服饰局部重绘模块

功能：
- 基于已有小柔图片，只修改服饰
- 保持脸部/发型/姿势/背景 100% 不变
- 支持文字描述修改意见

使用方式：
python3 selfie_inpaint.py <原图路径> "<修改意见>" [频道] [target]
"""

import os
import sys
import json
import base64
import logging
import requests
import uuid
import time
from pathlib import Path
from typing import Optional, Tuple

from config import config, ConfigurationError, ALLOWED_IMAGE_DIRS

# ========== 常量定义 ==========
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
MAX_IMAGE_SIZE_MB = 10
MAX_PROMPT_LENGTH = 6000
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))

log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64（带压缩）"""
    from PIL import Image
    import io
    
    # 打开图片
    img = Image.open(image_path)
    
    # 转换为 RGB（处理 PNG 透明通道）
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    
    # 调整尺寸到 1024x1536 以内
    max_width = 1024
    max_height = 1536
    if img.width > max_width or img.height > max_height:
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    
    # 压缩到 4MB 以内
    max_size = 4 * 1024 * 1024  # 4MB
    quality = 85
    
    while True:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        size = buffer.tell()
        
        if size <= max_size or quality <= 10:
            break
        
        quality -= 5
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def build_inpaint_prompt(original_description: str, modification_request: str) -> str:
    """
    构建服饰局部重绘提示词
    
    Args:
        original_description: 原图描述（可选）
        modification_request: 用户修改意见
    
    Returns:
        完整的局部重绘提示词
    """
    instruction = """【服饰局部重绘 - 最高优先级】
这是一张"服饰修改"任务：
- **输入图**：小柔的已有照片
- **修改目标**：只修改服饰，其他一切保持不变

【保持不变的元素 - 权重 5.0】
- **脸部 100% 不变**：五官、妆容、表情完全保留
- **发型 100% 不变**：发型、发色、发长完全保留
- **姿势 100% 不变**：身体姿势、手部动作完全保留
- **背景 100% 不变**：场景、背景、道具完全保留
- **光影 100% 不变**：光源方向、色温、阴影完全保留

【只修改服饰】
- 根据用户描述修改服装
- 保持服装与场景的协调性
- 保持光影一致性
- 保持肤色统一性

【禁止】
- 禁止改变脸部特征
- 禁止改变发型
- 禁止改变姿势
- 禁止改变背景
- 禁止任何马赛克/模糊/雾化效果
"""

    quality_tags = "8K, (no watermark:5.0), (correct proportions:5.0)"
    
    negative_tags = """(worst quality, low quality:1.4), 
(watermark,text,logo,signature:5.0), 
(mosaic,blur,fog,pixelated:5.0), 
(face change:5.0), (hairstyle change:5.0), (pose change:5.0), (background change:5.0)"""

    full_prompt = f"""{instruction}

【用户修改意见】{modification_request}

【原图描述】{original_description if original_description else "保持原图一切不变，只修改服饰"}

{quality_tags}
{negative_tags}

Keep face/hairstyle/pose/background 100% unchanged. ONLY modify outfit according to user request. NO face change, NO hairstyle change, NO pose change, NO background change. Same lighting, same skin tone, same proportions. NO watermark, NO mosaic, NO blur."""

    return full_prompt


def generate_inpaint_image(
    image_path: Path, 
    prompt: str, 
    api_key: str, 
    max_retries: int = 2
) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7-image 进行服饰局部重绘
    
    Args:
        image_path: 原图路径
        prompt: 提示词
        api_key: API Key
        max_retries: 最大重试次数
    
    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    model_name = 'wan2.7-image'
    
    for attempt in range(max_retries + 1):
        try:
            input_image_base64 = get_image_base64(image_path)
            logger.info(f"🖼️ 使用原图进行服饰重绘，模型:{model_name} (尝试 {attempt + 1}/{max_retries + 1})")
            
            # Prompt 长度校验
            max_prompt_len = MAX_PROMPT_LENGTH
            if len(prompt) > max_prompt_len:
                logger.warning(f"⚠️ Prompt 过长 ({len(prompt)} > {max_prompt_len}),已截断")
                prompt = prompt[:max_prompt_len]
            
            # 图生图模式：原图 + 文字 prompt
            content = [
                {'image': input_image_base64},
                {'text': prompt}
            ]
            logger.info(f"🖼️ 图生图模式：原图 + 文字 prompt(只修改服饰)")
            
            payload = {
                'model': model_name,
                'input': {'messages': [{'role': 'user', 'content': content}]},
                'parameters': {
                    'prompt_extend': False,
                    'watermark': False,
                    'n': 1,
                    'enable_interleave': False,
                    'size': '1536*2048',
                    'image_strength': 0.7,  # 原图影响力较强
                    'denoising_strength': 0.5,  # 去噪强度适中，只改服饰
                }
            }
            
            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'X-DashScope-DataInspection': '{\"input\":\"disable\",\"output\":\"disable\"}',
                    'X-DashScope-Log': 'disable',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}'
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
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
            
        except Exception as e:
            logger.error(f"❌ {model_name} 错误:{e}")
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
    
    return (model_name, None)


def send_to_feishu(image_url: str, caption: str, target: str) -> bool:
    """发送图片到飞书"""
    try:
        # 下载图片到临时文件
        temp_dir = Path("/tmp/openclaw")
        temp_dir.mkdir(mode=0o700, exist_ok=True)
        
        temp_file = temp_dir / f'inpaint_{uuid.uuid4().hex[:8]}.jpg'
        
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            logger.error(f"❌ 下载图片失败:{response.status_code}")
            return False
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        # 上传到飞书
        app_id = os.environ.get('FEISHU_APP_ID', '')
        app_secret = os.environ.get('FEISHU_APP_SECRET', '')
        
        if not app_id or not app_secret:
            logger.error("❌ 未配置飞书 APP_ID 或 APP_SECRET")
            return False
        
        # 获取 access_token
        token_response = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            headers={"Content-Type": "application/json"},
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        )
        token_data = token_response.json()
        access_token = token_data.get('tenant_access_token', '')
        
        if not access_token:
            logger.error(f"❌ 获取飞书 access_token 失败:{token_data}")
            return False
        
        # 上传图片
        files = {'image': (temp_file.name, open(temp_file, 'rb'), 'image/jpeg')}
        upload_response = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/images',
            headers={"Authorization": f"Bearer {access_token}"},
            files=files,
            timeout=30
        )
        upload_data = upload_response.json()
        image_key = upload_data.get('data', {}).get('image_key', '')
        
        if not image_key:
            logger.error(f"❌ 飞书图片上传失败:{upload_data}")
            return False
        
        logger.info(f"✅ 飞书图片上传成功:{image_key}")
        
        # 标准化用户 ID（支持所有格式）
        from config import normalize_feishu_target
        try:
            receive_id, receive_id_type = normalize_feishu_target(target)
        except ValueError as e:
            logger.error(f"用户 ID 格式错误：{e}")
            return False
        
        # 发送消息
        message_data = {
            "receive_id": receive_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key})
        }
        
        response = requests.post(
            f'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}',
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=message_data,
            timeout=30
        )
        
        result = response.json()
        if result.get('code') == 0:
            logger.info("✅ 飞书消息发送成功")
            return True
        else:
            logger.error(f"❌ 飞书消息发送失败:{result}")
            return False
        
    except Exception as e:
        logger.error(f"❌ 发送异常:{e}")
        return False


def generate_fashion_inpaint(
    image_path: str, 
    modification_request: str,
    caption: str = "这是修改服饰后的～", 
    channel: Optional[str] = None, 
    target: Optional[str] = None
) -> bool:
    """
    服饰局部重绘主函数
    
    Args:
        image_path: 原图路径
        modification_request: 用户修改意见
        caption: 配文
        channel: 频道
        target: 目标用户
    
    Returns:
        成功返回 True，失败返回 False
    """
    try:
        # 1. 加载 API Key
        api_key = os.environ.get('DASHSCOPE_API_KEY', '')
        if not api_key:
            # 尝试从配置文件加载
            config_file = Path.home() / '.openclaw' / 'openclaw.json'
            if config_file.exists():
                with open(config_file) as f:
                    cfg = json.load(f)
                    api_key = cfg.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
        
        if not api_key:
            logger.error("❌ 未找到 API Key")
            return False
        
        logger.info("✅ API Key 已加载")
        
        # 2. 验证图片路径
        img_path = Path(image_path)
        if not img_path.exists():
            logger.error(f"❌ 图片不存在:{image_path}")
            return False
        
        # 安全检查
        is_allowed = any(
            str(img_path.resolve()).startswith(str(base_dir.resolve()))
            for base_dir in ALLOWED_IMAGE_DIRS
        )
        if not is_allowed:
            logger.error(f"⚠️ 图片路径不在允许范围内:{image_path}")
            return False
        
        logger.info("✅ 原图验证通过")
        
        # 3. 构建提示词
        prompt = build_inpaint_prompt('', modification_request)
        logger.info(f"📝 修改意见:{modification_request}")
        
        # 4. 生成图片
        logger.info("🎨 服饰重绘生成中...")
        result = generate_inpaint_image(img_path, prompt, api_key)
        
        if not result[1]:
            logger.error("❌ 生成失败")
            return False
        
        logger.info("✅ 生成成功")
        
        # 5. 发送到飞书
        if channel == 'feishu' and target:
            logger.info(f"📤 发送到:feishu")
            if send_to_feishu(result[1], caption, target):
                logger.info("✅ 发送成功")
                return True
            else:
                logger.error("❌ 发送失败")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 错误:{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import time
    
    if len(sys.argv) < 3:
        print("用法:")
        print("  服饰重绘:python3 selfie_inpaint.py <原图路径> \"<修改意见>\" [频道] [target]")
        print("  示例:python3 selfie_inpaint.py /path/to/image.jpg \"换成红色裙子\" feishu ou_xxx")
        sys.exit(1)
    
    image_path = sys.argv[1]
    modification_request = sys.argv[2]
    channel = sys.argv[3] if len(sys.argv) > 3 else None
    caption = sys.argv[4] if len(sys.argv) > 4 else "这是修改服饰后的～"
    target = sys.argv[5] if len(sys.argv) > 5 else os.environ.get('AEVIA_TARGET')
    
    success = generate_fashion_inpaint(image_path, modification_request, caption, channel, target)
    sys.exit(0 if success else 1)
