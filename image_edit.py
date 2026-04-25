#!/usr/bin/env python3
"""image_edit.py - 图像编辑模块

基于参考图 + 文字指令进行图像编辑
使用 wan2.7-image 的 multimodal 能力
"""

import sys
import os
import time
import requests
import base64
import mimetypes
from pathlib import Path
from typing import Optional

# 导入统一配置
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir / 'scripts'))
try:
    from config import config
except ImportError:
    print("❌ 无法导入 config 模块")
    sys.exit(1)

API_TIMEOUT = 120
MAX_PROMPT_LENGTH = 6000

def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64"""
    file_size = image_path.stat().st_size
    if file_size > 20 * 1024 * 1024:
        raise ValueError(f"图片文件过大:{file_size / 1024 / 1024:.2f}MB(限制 20MB)")
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = 'image/jpeg'
    with open(image_path, 'rb') as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"

def build_edit_prompt(edit_instruction: str) -> str:
    """
    构建图像编辑 prompt
    
    核心原则：只修改用户指令指定的内容，其他一切保持不变
    """
    return f"""【系统指令 - 严格遵循】
**只修改用户指定的内容，其他一切保持不变**

【用户编辑指令】
{edit_instruction}

【必须严格保持 - 禁止修改】
- 场景背景：完全保持不变
- 人物身份：五官、脸型、发型完全不变
- 人物姿势：动作、角度、朝向完全不变
- 光影效果：光源方向、色温、氛围完全不变
- 构图视角：镜头角度、景深完全不变
- 其余内容：除用户指令外的所有内容完全不变

【执行要求】
- 只修改用户指令明确指定的部分
- 未提及的内容绝对不能修改
- 修改区域与原始区域自然融合
- 无拼贴感、无编辑痕迹

【禁止事项】
- 禁止修改背景
- 禁止修改人物五官/脸型/发型
- 禁止修改人物姿势/动作
- 禁止修改光影/色温
- 禁止修改构图/视角
- 禁止添加用户未要求的内容

【质量标准】
- 编辑区域自然过渡
- 光影一致、色彩协调
- 照片级真实感
- 8K 超高清，无水印"""

def generate_image_edit(reference_image_path: str, edit_instruction: str) -> Optional[str]:
    """
    图像编辑：参考图 + 文字指令 → 编辑后的新图
    使用 wan2.7-image 的 multimodal 能力
    """
    try:
        api_key = config.get_api_key()
        ref_path = Path(reference_image_path)
        
        if not ref_path.exists():
            print(f"❌ 参考图不存在:{reference_image_path}")
            return None
        
        # 构建 prompt
        prompt = build_edit_prompt(edit_instruction)
        
        # 读取参考图
        ref_base64 = get_image_base64(ref_path)
        
        # 构建 multimodal 请求
        content = [
            {'image': ref_base64},      # 参考图
            {'text': prompt}            # 编辑指令
        ]
        
        payload = {
            'model': 'wan2.7-image',
            'input': {'messages': [{'role': 'user', 'content': content}]},
            'parameters': {
                'prompt_extend': False,  # 关闭提示词扩写，只用用户原始指令
                'watermark': False,
                'n': 1,
                'enable_interleave': False,
                'size': '1536*2048'  # 3:4 竖版高清
            }
        }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}'
        }
        
        print(f"✏️ 图像编辑模式")
        print(f"📝 编辑指令:{edit_instruction}")
        print(f"🚀 wan2.7-image 生成中...")
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers=headers,
            json=payload,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            result_json = response.json()
            if result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    print(f"✅ 生成成功")
                    return image_url
        
        print(f"❌ 生成失败:{response.status_code}")
        print(f"响应:{response.text[:200]}")
        return None
        
    except Exception as e:
        print(f"❌ 错误:{e}")
        return None

def save_image(image_url: str, output_dir: str = "/tmp/xiaorou_generated") -> Optional[str]:
    """保存图片到本地"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        output_file = output_path / f"edited_{int(time.time())}.jpg"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(image_url, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            with open(output_file, "wb") as f:
                f.write(resp.content)
            print(f"✅ 图片已保存到：{output_file}")
            print(f"📊 文件大小：{len(resp.content) / 1024:.1f}KB")
            return str(output_file)
        
        return None
    except Exception as e:
        print(f"❌ 保存失败:{e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 image_edit.py <参考图路径> <编辑指令>")
        print("示例:")
        print("  python3 image_edit.py test.jpg 把外套脱掉")
        sys.exit(1)
    
    reference_image = sys.argv[1]
    edit_instruction = sys.argv[2]
    
    # 生成
    image_url = generate_image_edit(reference_image, edit_instruction)
    
    if image_url:
        # 保存
        output_file = save_image(image_url)
        if output_file:
            print(f"\n🎉 图像编辑完成！")
            print(f"📁 输出文件：{output_file}")
            sys.exit(0)
    
    sys.exit(1)
