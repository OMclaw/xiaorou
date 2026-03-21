#!/usr/bin/env python3
# selfie.py - 自拍生成（基于小柔头像的图生图）

import dashscope
from dashscope import ImageSynthesis, MultiModalConversation
import os
import sys
import json
import base64
from pathlib import Path

# 配置
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
CHARACTER_NAME = os.environ.get('AEVIA_CHARACTER_NAME', '小柔')
SCRIPT_DIR = Path(__file__).parent
# 小柔默认头像（本地文件）- 使用上级目录的 assets
DEFAULT_CHARACTER_PATH = SCRIPT_DIR.parent / 'assets' / 'default-character.png'

def get_image_base64(image_path):
    """将本地图片转换为 base64"""
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f"data:image/png;base64,{image_data}"

def generate_selfie(context, caption="给你看看我现在的样子~", channel=None):
    """
    使用 wan2.6-image 图生图生成自拍
    
    Args:
        context: 场景描述
        caption: 配文
        channel: 发送频道
    """
    if not DASHSCOPE_API_KEY:
        print("❌ 请设置 DASHSCOPE_API_KEY 环境变量")
        sys.exit(1)
    
    # 检查头像文件是否存在
    if not DEFAULT_CHARACTER_PATH.exists():
        print(f"❌ 未找到小柔头像文件：{DEFAULT_CHARACTER_PATH}")
        sys.exit(1)
    
    dashscope.api_key = DASHSCOPE_API_KEY
    
    # 判断模式
    if any(kw in context.lower() for kw in ['穿', '衣服', '穿搭', '全身', '镜子']):
        mode = "mirror"
        prompt = f"在对镜自拍，{context}，全身照，镜子反射，自然光线，真实感，高清"
    else:
        mode = "direct"
        prompt = f"{context}，眼神直视镜头，微笑，手臂伸出拿手机，背景虚化，真实感，高清"
    
    print(f"📸 模式：{mode}")
    print(f"📝 提示词：{prompt}")
    
    # 将本地头像转换为 base64
    input_image_base64 = get_image_base64(DEFAULT_CHARACTER_PATH)
    print(f"🖼️ 使用本地头像：{DEFAULT_CHARACTER_PATH}")
    
    # 构建消息（使用 base64 图片）
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
        # 调用 wan2.6-image（使用官方推荐的 API 格式）
        print("🎨 调用 wan2.6-image 生成...")
        
        # 构建完整的请求参数
        import requests
        
        payload = {
            'model': 'wan2.6-image',
            'input': {
                'messages': messages
            },
            'parameters': {
                'prompt_extend': True,  # 自动优化提示词
                'watermark': False,      # 不加水印
                'n': 1,
                'enable_interleave': False,
                'size': '2K'  # 最高分辨率
            }
        }
        
        headers = {
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers=headers,
            json=payload
        )
        
        result_json = response.json()
        
        # 检查是否成功
        if response.status_code == 200 and result_json.get('output'):
            # 获取生成的图片 URL
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                image_url = output['choices'][0]['message']['content'][0]['image']
                print(f"✅ 生成成功：{image_url}")
                
                # 发送到频道
                if channel:
                    print(f"📤 发送到：{channel}")
                    os.system(f'openclaw message send --action send --channel "{channel}" --message "{caption}" --media "{image_url}"')
                
                return image_url
            else:
                print(f"❌ 生成失败：{result_json}")
                sys.exit(1)
        else:
            print(f"❌ 生成失败：{result_json}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 selfie.py <场景描述> [频道] [配文]")
        print("示例：python3 selfie.py '在咖啡厅喝咖啡' feishu '给你看看我现在的样子~'")
        sys.exit(1)
    
    context = sys.argv[1]
    channel = sys.argv[2] if len(sys.argv) > 2 else None
    caption = sys.argv[3] if len(sys.argv) > 3 else "给你看看我现在的样子~"
    
    generate_selfie(context, caption, channel)
