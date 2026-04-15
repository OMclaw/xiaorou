#!/usr/bin/env python3
"""zimage_avatar.py - 小柔 AI 头像生成模块（Z-image 极速版）"""

import os, sys, json, time, requests, base64
from pathlib import Path

def get_api_key():
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key: return api_key
    config_file = Path.home() / '.openclaw/openclaw.json'
    if config_file.exists():
        config = json.loads(config_file.read_text())
        api_key = config.get('models',{}).get('providers',{}).get('dashscope',{}).get('apiKey','') or config.get('skills',{}).get('entries',{}).get('xiaorou',{}).get('env',{}).get('DASHSCOPE_API_KEY','')
        if api_key: return api_key
    raise Exception("API Key 未配置")

def generate_avatar(prompt, size="1536*1536"):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {get_api_key()}"}
    data = {"model": "z-image-turbo", "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]}, "parameters": {"prompt_extend": False, "size": size}}
    r = requests.post(url, headers=headers, json=data, timeout=120)
    if r.status_code != 200: raise Exception(f"API 失败：{r.status_code}")
    result = r.json()
    if "code" in result: raise Exception(f"生成失败：{result.get('code')} - {result.get('message')}")
    return result["output"]["choices"][0]["message"]["content"][0]["image"]

def download_image(image_url):
    r = requests.get(image_url, timeout=60)
    if r.status_code != 200: raise Exception(f"下载失败：{r.status_code}")
    return r.content

def generate_xiaorou_avatar(style="default"):
    prompts = {"default": "小柔，AI 虚拟伴侣，温暖亲切的东亚年轻女性，温柔微笑，黑色长直发，简约白色上衣，柔和自然光线，清新自然风格，高分辨率肖像，专业摄影，8K 超高清，电影级布光，背景虚化，真实皮肤纹理，自然妆容", "cute": "小柔，可爱 AI 虚拟伴侣，甜美笑容的东亚年轻女性，黑色长发双马尾，粉色系服装，明亮大眼睛，柔和暖色光线，可爱风格，高分辨率肖像，专业摄影，8K 超高清，背景虚化，清新可爱", "elegant": "小柔，优雅 AI 虚拟伴侣，知性温柔的东亚年轻女性，黑色长发盘起，优雅浅色连衣裙，精致妆容，柔和自然光线，优雅风格，高分辨率肖像，专业摄影，8K 超高清，电影级布光，背景虚化", "casual": "小柔，休闲 AI 虚拟伴侣，自然亲切的东亚年轻女性，黑色长发自然披肩，休闲舒适服装，自然微笑，户外自然光线，休闲风格，高分辨率肖像，专业摄影，8K 超高清，真实自然，背景虚化"}
    return generate_avatar(prompts.get(style, prompts["default"]).strip())

if __name__ == '__main__':
    if len(sys.argv) < 2: print("用法：python3 zimage_avatar.py [提示词 | 风格]"); sys.exit(1)
    style = sys.argv[1].lower()
    image_url = generate_xiaorou_avatar(style) if style in ["default","cute","elegant","casual"] else generate_avatar(" ".join(sys.argv[1:]))
    # 下载图片
    img_data = download_image(image_url)
    # 保存到临时文件
    tmp_path = f"/tmp/xiaorou_{int(time.time())}.png"
    with open(tmp_path, 'wb') as f: f.write(img_data)
    print(tmp_path)
