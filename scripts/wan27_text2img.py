#!/usr/bin/env python3
"""wan27_text2img.py - 万相 2.7 文生图（纯文字描述，不使用小柔头像）"""

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

def generate(prompt, size="1024*1024"):
    """wan2.7-image 文生图 API"""
    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {get_api_key()}'}
    # 使用 wan2.7-image 模型，纯文生图（不传参考图）
    data = {
        'model': 'wan2.7-image',
        'input': {
            'messages': [{
                'role': 'user',
                'content': [{'text': prompt}]
            }]
        },
        'parameters': {
            'prompt_extend': False,
            'size': size
        }
    }
    r = requests.post(url, headers=headers, json=data, timeout=180)
    if r.status_code != 200:
        raise Exception(f'API 失败：{r.status_code} - {r.text}')
    result = r.json()
    if 'code' in result:
        raise Exception(f'生成失败：{result.get("code")} - {result.get("message")}')
    image_url = result['output']['choices'][0]['message']['content'][0]['image']
    # 下载图片
    img_data = requests.get(image_url, timeout=60).content
    tmp_path = f'/tmp/xiaorou_{int(time.time())}.png'
    with open(tmp_path, 'wb') as f: f.write(img_data)
    return tmp_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法：python3 wan27_text2img.py "提示词"')
        sys.exit(1)
    prompt = ' '.join(sys.argv[1:])
    tmp_path = generate(prompt)
    print(tmp_path)
