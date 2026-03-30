#!/usr/bin/env python3
"""image_analyzer.py - 参考图分析模块 (使用 qwen3.5-plus 视觉能力)"""

import dashscope
import os
import sys
import json
import base64
import logging
import re
import requests
from pathlib import Path
from typing import Optional, Tuple

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
    使用 qwen3.5-plus 分析图片，提取详细的 prompt 描述
    
    Args:
        image_path: 图片路径
        api_key: DashScope API Key
    
    Returns:
        详细的图片描述 prompt
    """
    import dashscope
    from dashscope import MultiModalConversation
    
    dashscope.api_key = api_key
    
    # 读取图片为 base64
    try:
        image_base64 = get_image_base64(image_path)
    except Exception as e:
        raise ImageAnalysisError(f"读取图片失败：{e}")
    
    # 构建分析 prompt
    analysis_prompt = """请详细分析这张图片，提取用于 AI 绘画的 prompt 描述。请包含以下要素：

1. **场景环境**：室内/室外、具体地点、背景元素
2. **人物姿态**：站姿/坐姿、手部动作、身体角度、与镜头的关系
3. **服装穿搭**：衣服款式、颜色、风格、配饰
4. **妆容发型**：发型、发色、妆容特点
5. **光线氛围**：自然光/人造光、光线方向、整体色调
6. **构图特点**：拍摄角度、景深、构图方式
7. **风格标签**：如 ins 风、小红书风格、网红风、日系、韩系等

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


def extract_style_keywords(description: str) -> str:
    """
    从图片描述中提取风格关键词，用于后续生成
    
    Args:
        description: 图片分析结果
    
    Returns:
        精简的风格关键词
    """
    # 提取风格相关关键词
    style_keywords = []
    
    # 场景
    if any(kw in description for kw in ['咖啡厅', '咖啡店', '室内', '窗边']):
        style_keywords.append('咖啡厅场景')
    if any(kw in description for kw in ['海边', '海滩', '沙滩', '海洋']):
        style_keywords.append('海边场景')
    if any(kw in description for kw in ['街道', '街拍', '城市', '马路']):
        style_keywords.append('城市街拍')
    if any(kw in description for kw in ['公园', '花园', '户外', '自然']):
        style_keywords.append('户外自然')
    
    # 风格
    if any(kw in description for kw in ['ins 风', 'ins']):
        style_keywords.append('ins 风')
    if any(kw in description for kw in ['小红书', '网红']):
        style_keywords.append('小红书风格')
    if any(kw in description for kw in ['日系', '小清新']):
        style_keywords.append('日系清新')
    if any(kw in description for kw in ['韩系', '韩式']):
        style_keywords.append('韩系风格')
    if any(kw in description for kw in ['复古', '怀旧']):
        style_keywords.append('复古风')
    
    # 光线
    if any(kw in description for kw in ['逆光', '背光']):
        style_keywords.append('逆光效果')
    if any(kw in description for kw in ['侧光', '侧逆光']):
        style_keywords.append('侧光')
    if any(kw in description for kw in ['柔光', '柔和']):
        style_keywords.append('柔光')
    
    return '，'.join(style_keywords) if style_keywords else ''


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
        
        # 分析图片
        description = analyze_image(image_path, api_key)
        logger.info(f"📝 分析结果：{description[:100]}...")
        
        # 提取风格关键词
        style_keywords = extract_style_keywords(description)
        
        # 组合最终 prompt
        final_prompt = description
        if style_keywords:
            final_prompt += f"，{style_keywords}"
        
        # 添加网红风格基础标签
        final_prompt += "，网红风格，精致妆容，时尚穿搭，8K 超高清，专业摄影"
        
        return final_prompt
        
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
