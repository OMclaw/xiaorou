#!/usr/bin/env python3
# selfie.py - 自拍生成（基于小柔头像的图生图）

import dashscope
from dashscope import ImageSynthesis, MultiModalConversation
import os
import sys
import json

# 配置
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
CHARACTER_NAME = os.environ.get('AEVIA_CHARACTER_NAME', '小柔')
# 小柔默认头像 URL
DEFAULT_CHARACTER_URL = "https://dashscope-a717.oss-accelerate.aliyuncs.com/1d/bc/20260321/c8f05150/46631868-oD8cWYVo_60286cb62a07.png?Expires=1774149486&OSSAccessKeyId=LTAI5tPxpiCM2hjmWrFXrym1&Signature=JOd0ViB1Xe%2FtC%2BKzFYiJ3hq%2BV%2BA%3D"

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
    
    # 构建消息
    messages = [
        {
            'role': 'user',
            'content': [
                {'image': DEFAULT_CHARACTER_URL},
                {'text': prompt}
            ]
        }
    ]
    
    try:
        # 调用 wan2.6-image
        print("🎨 调用 wan2.6-image 生成...")
        result = MultiModalConversation.call(
            model='wan2.6-image',
            messages=messages,
            size='2048*2048',  # 高分辨率
            n=1
        )
        
        if result.status_code == 200 and result.output:
            # 获取生成的图片 URL
            image_url = result.output.choices[0].message.content[0]['image']
            print(f"✅ 生成成功：{image_url}")
            
            # 发送到频道
            if channel:
                print(f"📤 发送到：{channel}")
                os.system(f'openclaw message send --action send --channel "{channel}" --message "{caption}" --media "{image_url}"')
            
            return image_url
        else:
            print(f"❌ 生成失败：{result}")
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
