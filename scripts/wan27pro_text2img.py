#!/usr/bin/env python3
"""wan27pro_text2img.py - 万相 2.7-image-pro 文生图（4K 高清）"""

import os, sys, json, time, requests
from pathlib import Path

def get_api_key():
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key: return api_key
    config_file = Path.home() / '.openclaw/openclaw.json'
    if config_file.exists():
        config = json.loads(config_file.read_text())
        api_key = config.get('models',{}).get('providers',{}).get('dashscope',{}).get('apiKey','') or config.get('skills',{}).get('entries',{}).get('xiaorou',{}).get('env',{}).get('DASHSCOPE_API_KEY','')
        if api_key: return api_key
    raise Exception('API Key 未配置')

def generate(prompt, size="1024*1024", n=1):
    """wan2.7-image-pro 文生图 API"""
    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {get_api_key()}'}
    data = {
        'model': 'wan2.7-image-pro',
        'input': {
            'messages': [{
                'role': 'user',
                'content': [{'text': prompt}]
            }]
        },
        'parameters': {
            'size': size,
            'n': n,
            'watermark': False,
            'thinking_mode': True
        }
    }
    print(f"🎨 开始生成 (wan2.7-image-pro, {size}, {n}张)...")
    r = requests.post(url, headers=headers, json=data, timeout=300)
    if r.status_code != 200:
        raise Exception(f'API 失败：{r.status_code} - {r.text}')
    result = r.json()
    if 'code' in result:
        raise Exception(f'生成失败：{result.get("code")} - {result.get("message")}')
    
    # 提取图片 URLs
    content = result['output']['choices'][0]['message']['content']
    image_urls = [item['image'] for item in content if 'image' in item]
    
    # 下载图片
    paths = []
    for i, image_url in enumerate(image_urls):
        img_data = requests.get(image_url, timeout=120).content
        tmp_path = f'/tmp/xiaorou_{int(time.time())}_{i+1}.png'
        with open(tmp_path, 'wb') as f: f.write(img_data)
        paths.append(tmp_path)
        print(f"✅ 下载完成：{tmp_path}")
    
    return paths

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法：python3 wan27pro_text2img.py "提示词" [size] [n]')
        print('示例：python3 wan27pro_text2img.py "提示词" 1024*1024 4')
        sys.exit(1)
    prompt = ' '.join(sys.argv[1:])
    size = sys.argv[2] if len(sys.argv) > 2 else "1024*1024"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    paths = generate(prompt, size, n)
    print(f"\n✅ 生成完成！共 {len(paths)} 张图片")
    for p in paths: print(p)
