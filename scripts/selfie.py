#!/usr/bin/env python3
"""
selfie.py - 自拍生成模块

基于小柔头像的图生图功能，使用 Wan2.6-image 模型生成各种场景的自拍照片。

功能:
    - 根据场景描述生成自拍
    - 支持对镜自拍和直接自拍两种模式
    - 自动发送到指定频道

使用示例:
    python3 selfie.py "在咖啡厅喝咖啡" feishu "给你看看我现在的样子~"

依赖:
    - dashscope: 阿里云百炼 SDK
    - requests: HTTP 请求库

安全特性:
    - 输入验证和清理
    - 路径安全验证（防止目录遍历）
    - API Key 脱敏处理
    - 完善的错误处理
"""

import dashscope
from dashscope import ImageSynthesis, MultiModalConversation
import os
import sys
import json
import base64
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

# ============================================
# 配置常量
# ============================================
DEFAULT_IMAGE_SIZE = "2K"  # 最高分辨率
DEFAULT_WATERMARK = False  # 不加水印
PROMPT_EXTEND = True  # 自动优化提示词
MAX_INPUT_LENGTH = 500  # 最大输入长度

# ============================================
# 日志配置
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ============================================
# 安全函数：路径验证
# ============================================
def safe_resolve_path(base_dir: Path, relative_path: str) -> Path:
    """
    安全地解析路径，防止目录遍历攻击
    
    Args:
        base_dir: 基目录
        relative_path: 相对路径
        
    Returns:
        解析后的绝对路径
        
    Raises:
        ValueError: 如果路径超出允许范围
    """
    # 解析绝对路径
    resolved = (base_dir / relative_path).resolve()
    
    # 确保路径在基目录内
    try:
        resolved.relative_to(base_dir.resolve())
        return resolved
    except ValueError:
        raise ValueError(f"路径超出允许范围：{relative_path}")


def validate_path_security(path: Path, base_dir: Path) -> bool:
    """
    验证路径是否在允许的目录内
    
    Args:
        path: 要验证的路径
        base_dir: 允许的基目录
        
    Returns:
        True 如果路径安全，False 否则
    """
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


# ============================================
# 安全函数：输入验证
# ============================================
def sanitize_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    清理和验证用户输入
    
    Args:
        text: 原始输入
        max_length: 最大长度限制
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 长度限制
    if len(text) > max_length:
        logger.warning(f"输入过长 ({len(text)} 字符)，已截断至 {max_length}")
        text = text[:max_length]
    
    # 移除危险字符（保留中文、英文、数字和常见标点）
    # 过滤掉可能用于命令注入的字符
    dangerous_chars = r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f`$(){};|&!\\]'
    text = re.sub(dangerous_chars, '', text)
    
    return text


def validate_channel(channel: Optional[str]) -> Optional[str]:
    """
    验证频道参数（白名单验证）
    
    Args:
        channel: 频道名称
        
    Returns:
        有效的频道名称或 None
    """
    if not channel:
        return None
    
    valid_channels = {'feishu', 'telegram', 'discord', 'whatsapp'}
    if channel.lower() in valid_channels:
        return channel.lower()
    else:
        logger.warning(f"未知频道：{channel}，忽略")
        return None


# ============================================
# 配置验证
# ============================================
class ConfigurationError(Exception):
    """配置错误异常类"""
    pass


class FileNotFoundError(Exception):
    """文件未找到异常类"""
    pass


def validate_config() -> str:
    """
    验证 API Key 配置
    
    Returns:
        有效的 API Key
        
    Raises:
        ConfigurationError: 如果配置无效
    """
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    
    if not api_key:
        raise ConfigurationError("API Key 未设置，请配置 DASHSCOPE_API_KEY 环境变量")
    
    # 验证 API Key 格式
    if not re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
        logger.warning("API Key 格式可能不正确")
    
    return api_key


def validate_character_image() -> Path:
    """
    验证头像文件是否存在且安全
    
    Returns:
        头像文件路径
        
    Raises:
        FileNotFoundError: 如果文件不存在或无效
    """
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    character_path = safe_resolve_path(project_root, 'assets/default-character.png')
    
    # 验证文件存在
    if not character_path.exists():
        raise FileNotFoundError(f"头像文件不存在：{character_path}")
    
    # 验证是普通文件
    if not character_path.is_file():
        raise FileNotFoundError(f"头像路径不是有效文件：{character_path}")
    
    # 检查文件权限（不过于开放）
    file_stat = character_path.stat()
    if file_stat.st_mode & 0o022:  # 其他人可写
        logger.warning(f"⚠️ 警告：头像文件权限过于开放")
    
    return character_path


# ============================================
# 工具函数
# ============================================
def get_image_base64(image_path: Path) -> str:
    """
    将本地图片转换为 base64 编码
    
    Args:
        image_path: 图片路径
        
    Returns:
        base64 编码的图片数据 URI
        
    Raises:
        FileNotFoundError: 如果文件不存在
        IOError: 如果读取失败
    """
    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        return f"data:image/png;base64,{image_data}"
    except FileNotFoundError:
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    except IOError as e:
        raise IOError(f"读取图片失败：{e}")


def mask_api_key(api_key: str) -> str:
    """
    脱敏 API Key（用于日志）
    
    Args:
        api_key: 原始 API Key
        
    Returns:
        脱敏后的 API Key
    """
    if len(api_key) > 10:
        return f"{api_key[:5]}...{api_key[-5:]}"
    return "***"


def build_prompt(context: str) -> Tuple[str, str]:
    """
    根据场景描述构建提示词
    
    Args:
        context: 场景描述
        
    Returns:
        (模式，提示词) 元组
    """
    context_lower = context.lower()
    
    # 判断模式
    mirror_keywords = ['穿', '衣服', '穿搭', '全身', '镜子']
    if any(kw in context_lower for kw in mirror_keywords):
        mode = "mirror"
        prompt = f"在对镜自拍，{context}，全身照，镜子反射，自然光线，真实感，高清"
    else:
        mode = "direct"
        prompt = f"{context}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"
    
    return mode, prompt


def call_image_api(image_path: Path, prompt: str, api_key: str) -> str:
    """
    调用图像生成 API
    
    Args:
        image_path: 输入图片路径
        prompt: 提示词
        api_key: API Key
        
    Returns:
        生成图片的 URL
        
    Raises:
        Exception: 如果 API 调用失败
    """
    # 设置 API Key
    dashscope.api_key = api_key
    
    # 将本地头像转换为 base64
    input_image_base64 = get_image_base64(image_path)
    logger.info(f"🖼️ 使用本地头像")
    
    # 构建消息
    messages = [
        {
            'role': 'user',
            'content': [
                {'image': input_image_base64},
                {'text': prompt}
            ]
        }
    ]
    
    try:
        # 调用 wan2.6-image
        logger.info("🎨 调用 wan2.6-image 生成...")
        
        import requests
        
        payload = {
            'model': 'wan2.6-image',
            'input': {
                'messages': messages
            },
            'parameters': {
                'prompt_extend': PROMPT_EXTEND,
                'watermark': DEFAULT_WATERMARK,
                'n': 1,
                'enable_interleave': False,
                'size': DEFAULT_IMAGE_SIZE
            }
        }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers=headers,
            json=payload,
            timeout=120  # 添加超时限制
        )
        
        result_json = response.json()
        
        # 检查是否成功
        if response.status_code == 200 and result_json.get('output'):
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info(f"✅ 生成成功")
                return image_url
            else:
                raise Exception(f"生成失败：{result_json}")
        else:
            raise Exception(f"API 错误 ({response.status_code}): {result_json}")
            
    except requests.exceptions.Timeout:
        raise Exception("API 请求超时")
    except requests.exceptions.RequestException as e:
        raise Exception(f"网络错误：{e}")


def send_to_channel(image_url: str, caption: str, channel: str) -> bool:
    """
    发送图片到指定频道
    
    Args:
        image_url: 图片 URL
        caption: 配文
        channel: 频道名称
        
    Returns:
        True 如果发送成功，False 否则
    """
    try:
        logger.info(f"📤 发送到：{channel}")
        os.system(f'openclaw message send --action send --channel "{channel}" --message "{caption}" --media "{image_url}"')
        return True
    except Exception as e:
        logger.error(f"发送失败：{e}")
        return False


# ============================================
# 主函数：生成自拍
# ============================================
def generate_selfie(context: str, caption: str = "给你看看我现在的样子~", channel: Optional[str] = None) -> Optional[str]:
    """
    使用 wan2.6-image 图生图生成自拍
    
    Args:
        context: 场景描述
        caption: 配文
        channel: 发送频道
        
    Returns:
        生成图片的 URL，失败时返回 None
    """
    try:
        # 1. 验证配置
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载：{mask_api_key(api_key)}")
        
        # 2. 验证头像文件
        image_path = validate_character_image()
        logger.info(f"✅ 头像文件验证通过")
        
        # 3. 验证和清理输入
        context = sanitize_input(context)
        if not context:
            logger.error("无效的场景描述")
            return None
        
        # 4. 验证频道
        channel = validate_channel(channel)
        
        # 5. 构建提示词
        mode, prompt = build_prompt(context)
        logger.info(f"📸 模式：{mode}")
        logger.info(f"📝 提示词：{prompt}")
        
        # 6. 调用 API 生成图片
        image_url = call_image_api(image_path, prompt, api_key)
        
        # 7. 发送到频道
        if channel and image_url:
            send_to_channel(image_url, caption, channel)
        
        return image_url
        
    except ConfigurationError as e:
        logger.error(f"❌ 配置错误：{e}")
        return None
    except FileNotFoundError as e:
        logger.error(f"❌ 文件错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


# ============================================
# 命令行入口
# ============================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 selfie.py <场景描述> [频道] [配文]")
        print("示例：python3 selfie.py '在咖啡厅喝咖啡' feishu '给你看看我现在的样子~'")
        sys.exit(1)
    
    # 获取参数
    context = sys.argv[1]
    channel = sys.argv[2] if len(sys.argv) > 2 else None
    caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
    
    # 生成自拍
    result = generate_selfie(context, caption, channel)
    
    # 退出码
    sys.exit(0 if result else 1)
