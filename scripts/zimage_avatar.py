#!/usr/bin/env python3
"""
zimage_avatar.py - 小柔 AI 头像生成模块（基于 Z-image）

基于阿里云 Z-image 模型生成小柔头像
文档：https://help.aliyun.com/zh/model-studio/z-image-api-reference

使用方式：
    python3 scripts/zimage_avatar.py "小柔，AI 虚拟伴侣，温暖亲切"
"""

import os
import sys
import json
import time
import base64
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """获取 API Key"""
    # 环境变量优先
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key:
        return api_key
    
    # 从配置文件读取
    config_file = Path.home() / '.openclaw/openclaw.json'
    if config_file.exists():
        config = json.loads(config_file.read_text(encoding='utf-8'))
        api_key = (
            config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '') or
            config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
        )
        if api_key:
            return api_key
    
    raise Exception("API Key 未配置，请设置 DASHSCOPE_API_KEY 环境变量或配置文件")


def generate_avatar(
    prompt: str,
    size: str = "1024*1024",
    output_dir: Optional[str] = None,
    seed: Optional[int] = None
) -> Tuple[str, str]:
    """
    使用 Z-image 生成头像
    
    Args:
        prompt: 正向提示词
        size: 输出分辨率，默认 1024*1024
        output_dir: 输出目录，默认当前目录
        seed: 随机数种子，可选
    
    Returns:
        (图片本地路径，图片 URL)
    """
    api_key = get_api_key()
    
    # API 端点（北京地域）
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    
    # 请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 请求体
    data = {
        "model": "z-image-turbo",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        },
        "parameters": {
            "prompt_extend": False,  # 关闭智能改写，加快速度
            "size": size
        }
    }
    
    # 添加 seed（如果提供）
    if seed is not None:
        data["parameters"]["seed"] = seed
    
    logger.info(f"🎨 开始生成头像...")
    logger.info(f"📝 提示词：{prompt[:100]}...")
    logger.info(f"📐 分辨率：{size}")
    
    # 发送请求
    start_time = time.time()
    response = requests.post(url, headers=headers, json=data, timeout=120)
    elapsed = time.time() - start_time
    
    # 检查响应
    if response.status_code != 200:
        logger.error(f"❌ API 请求失败：{response.status_code}")
        logger.error(f"响应内容：{response.text}")
        raise Exception(f"API 请求失败：{response.status_code}")
    
    result = response.json()
    
    # 检查错误
    if "code" in result:
        logger.error(f"❌ 生成失败：{result.get('code')} - {result.get('message')}")
        raise Exception(f"生成失败：{result.get('code')} - {result.get('message')}")
    
    # 提取图片 URL
    try:
        image_url = result["output"]["choices"][0]["message"]["content"][0]["image"]
    except (KeyError, IndexError) as e:
        logger.error(f"❌ 解析响应失败：{e}")
        logger.error(f"响应内容：{json.dumps(result, ensure_ascii=False)}")
        raise Exception(f"解析响应失败：{e}")
    
    logger.info(f"✅ 生成成功！耗时：{elapsed:.2f}秒")
    logger.info(f"🔗 图片 URL: {image_url[:80]}...")
    
    # 下载图片
    local_path = download_image(image_url, output_dir)
    
    return local_path, image_url


def download_image(image_url: str, output_dir: Optional[str] = None) -> str:
    """
    下载图片到本地
    
    Args:
        image_url: 图片 URL
        output_dir: 输出目录
    
    Returns:
        本地文件路径
    """
    # 确定输出目录
    if output_dir is None:
        output_dir = "/tmp/xiaorou"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    timestamp = int(time.time())
    filename = f"zimage_avatar_{timestamp}.png"
    local_path = output_path / filename
    
    # 下载图片
    logger.info(f"⬇️ 下载图片到：{local_path}")
    
    response = requests.get(image_url, timeout=60)
    if response.status_code != 200:
        logger.error(f"❌ 下载失败：{response.status_code}")
        raise Exception(f"下载失败：{response.status_code}")
    
    # 保存文件
    with open(local_path, 'wb') as f:
        f.write(response.content)
    
    logger.info(f"✅ 下载完成：{local_path}")
    
    return str(local_path)


def generate_xiaorou_avatar(
    style: str = "default",
    output_dir: Optional[str] = None
) -> Tuple[str, str]:
    """
    生成小柔头像（预设风格）
    
    Args:
        style: 风格选择
            - "default": 默认温暖风格
            - "cute": 可爱风格
            - "elegant": 优雅风格
            - "casual": 休闲风格
        output_dir: 输出目录
    
    Returns:
        (图片本地路径，图片 URL)
    """
    # 预设提示词
    prompts = {
        "default": """
小柔，AI 虚拟伴侣，温暖亲切的东亚年轻女性，温柔微笑，黑色长直发，
穿着简约白色上衣，柔和自然光线，清新自然风格，
高分辨率肖像，专业摄影，8K 超高清，电影级布光，
背景虚化，浅景深，真实皮肤纹理，自然妆容
""",
        "cute": """
小柔，可爱 AI 虚拟伴侣，甜美笑容的东亚年轻女性，
黑色长发双马尾，穿着粉色系服装，明亮大眼睛，
柔和暖色光线，可爱风格，高分辨率肖像，
专业摄影，8K 超高清，背景虚化，清新可爱
""",
        "elegant": """
小柔，优雅 AI 虚拟伴侣，知性温柔的东亚年轻女性，
黑色长发盘起，穿着优雅浅色连衣裙，精致妆容，
柔和自然光线，优雅风格，高分辨率肖像，
专业摄影，8K 超高清，电影级布光，背景虚化
""",
        "casual": """
小柔，休闲 AI 虚拟伴侣，自然亲切的东亚年轻女性，
黑色长发自然披肩，穿着休闲舒适服装，自然微笑，
户外自然光线，休闲风格，高分辨率肖像，
专业摄影，8K 超高清，真实自然，背景虚化
"""
    }
    
    prompt = prompts.get(style, prompts["default"])
    
    logger.info(f"🎨 生成小柔头像（风格：{style}）...")
    
    return generate_avatar(
        prompt=prompt.strip(),
        size="1024*1024",
        output_dir=output_dir
    )


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：python3 zimage_avatar.py [提示词|风格]")
        print("示例：")
        print("  python3 zimage_avatar.py \"小柔，AI 虚拟伴侣，温暖亲切\"")
        print("  python3 zimage_avatar.py default  # 默认风格")
        print("  python3 zimage_avatar.py cute     # 可爱风格")
        print("  python3 zimage_avatar.py elegant  # 优雅风格")
        print("  python3 zimage_avatar.py casual   # 休闲风格")
        sys.exit(1)
    
    # 检查是否是预设风格
    style = sys.argv[1].lower()
    if style in ["default", "cute", "elegant", "casual"]:
        local_path, image_url = generate_xiaorou_avatar(style=style)
    else:
        # 使用自定义提示词
        prompt = " ".join(sys.argv[1:])
        local_path, image_url = generate_avatar(prompt=prompt)
    
    print(f"\n✅ 头像生成完成！")
    print(f"📁 本地路径：{local_path}")
    print(f"🔗 图片 URL: {image_url}")
