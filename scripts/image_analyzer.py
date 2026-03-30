#!/usr/bin/env python3
"""image_analyzer.py - 参考图分析模块 (使用 qwen3.5-plus 视觉能力)

分析参考图，提取场景、姿势、服装、光线等描述，用于后续图生图。
"""

import dashscope
import os
import sys
import json
import base64
import logging
import re
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception): pass
class ImageAnalysisError(Exception): pass


def validate_config() -> str:
    """验证并加载 API Key"""
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
    
    raise ConfigurationError("API Key 未设置")


def get_image_base64(image_path: str) -> str:
    """读取图片并转换为 base64"""
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{image_data}"


def analyze_image(image_path: str, api_key: str) -> str:
    """
    使用 qwen3.5-plus 分析参考图，提取场景、姿势、服装、光线等描述
    
    Args:
        image_path: 图片路径
        api_key: DashScope API Key
    
    Returns:
        详细的图片描述 prompt
    """
    import dashscope
    from dashscope import MultiModalConversation
    
    dashscope.api_key = api_key
    
    try:
        image_base64 = get_image_base64(image_path)
    except Exception as e:
        raise ImageAnalysisError(f"读取图片失败：{e}")
    
    # 构建分析 prompt - 提取场景、姿势、服装、光线等
    analysis_prompt = """请详细分析这张图片，提取用于 AI 绘画的 prompt 描述。请包含以下要素：

1. **场景环境**：室内/室外、具体地点、背景元素
2. **人物姿态**：站姿/坐姿/蹲姿、手部动作、身体角度、与镜头的关系
3. **服装穿搭**：衣服款式、颜色、风格、配饰
4. **妆容发型**：发型、发色、妆容特点
5. **光线氛围**：自然光/人造光、光线方向、整体色调
6. **构图特点**：拍摄角度、景深、构图方式

请用简洁的中文描述，要素之间用逗号分隔，适合作为 AI 绘画的 prompt。不需要评价图片，只需要客观描述视觉元素。"""

    messages = [{
        'role': 'user',
        'content': [
            {'image': image_base64},
            {'text': analysis_prompt}
        ]
    }]
    
    try:
        response = MultiModalConversation.call(
            model='qwen3.5-plus',
            messages=messages,
            api_key=api_key
        )
        
        if response.status_code == 200 and response.output:
            result = response.output.choices[0].message.content[0]['text']
            logger.info("✅ 图片分析成功")
            return result
        
        raise ImageAnalysisError(f"API 错误：{response.message}")
    
    except Exception as e:
        raise ImageAnalysisError(f"图片分析失败：{e}")


def build_reference_prompt(description: str) -> str:
    """
    基于参考图分析结果，构建用于图生图的 prompt
    
    Args:
        description: 参考图分析结果
    
    Returns:
        完整的 prompt，包含保持人物一致性的描述
    """
    # 基础风格标签 - 减少妆容感
    base_style = "网红风格，时尚穿搭，专业摄影，自然妆容，淡妆"
    
    # 真实感标签（v4.0.1 皮肤优化）- 强调自然
    realistic_tags = "真实摄影，自然光滑皮肤，清透肌肤，真实光影，柔和光线，生活照风格，无 AI 感，无塑料感，无黑点，无瑕疵，自然唇色，淡粉色嘴唇"
    
    # 质量标签
    quality_tags = "8K 超高清，电影级布光，细节丰富，色彩自然"
    
    # **关键**：三次强调保持输入图片的人物脸部特征（开头、中间、结尾）
    # 开头强调 - 最重要
    consistency_head = "【必须严格保持输入图片的人物脸部特征】原始五官、原始脸型、原始妆容风格，不要改变人物身份，必须使用输入图片的人物，严格保持原始人物的五官特征和脸型"
    
    # 中间强调
    consistency_mid = "严格保持输入图片人物的五官特征和脸型，不要改变她的眼睛、鼻子、嘴巴、眉毛形状，妆容风格必须与输入图片一致"
    
    # 结尾强调
    consistency_end = "必须严格保持输入图片的人物脸部一致性，不要改变她的五官和脸型，确保是同一个人"
    
    # 组合完整 prompt - 三次强调
    full_prompt = f"{consistency_head}，{base_style}，{description}，{consistency_mid}，{realistic_tags}，{quality_tags}，{consistency_end}"
    
    return full_prompt


def analyze_image_file(image_path: str) -> Optional[str]:
    """
    分析图片文件，返回优化后的 prompt
    
    Args:
        image_path: 图片路径
    
    Returns:
        优化后的 prompt，失败返回 None
    """
    try:
        api_key = validate_config()
        
        # 分析参考图
        description = analyze_image(image_path, api_key)
        logger.info(f"📝 分析结果：{description[:100]}...")
        
        # 构建用于图生图的 prompt
        prompt = build_reference_prompt(description)
        
        return prompt
        
    except (ConfigurationError, ImageAnalysisError) as e:
        logger.error(f"❌ 错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 image_analyzer.py <图片路径>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        logger.error(f"图片不存在：{image_path}")
        sys.exit(1)
    
    result = analyze_image_file(image_path)
    
    if result:
        print(result)
        sys.exit(0)
    else:
        sys.exit(1)
