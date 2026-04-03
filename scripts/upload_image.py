#!/usr/bin/env python3
"""upload_image.py - 图片上传工具

上传到阿里云 OSS 获取公网 URL
"""

import os
import sys
import json
import time
import requests
import hashlib
import base64
import hmac
from pathlib import Path
from typing import Optional


def get_oss_config():
    """获取 OSS 配置"""
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # 尝试从 skills 配置中读取
        oss_config = config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {})
        if oss_config.get('OSS_ACCESS_KEY_ID') and oss_config.get('OSS_ACCESS_KEY_SECRET'):
            return {
                'access_key_id': oss_config['OSS_ACCESS_KEY_ID'],
                'access_key_secret': oss_config['OSS_ACCESS_KEY_SECRET'],
                'bucket': oss_config.get('OSS_BUCKET', 'xiaorou-images'),
                'region': oss_config.get('OSS_REGION', 'cn-beijing')
            }
    
    # 默认配置（需要用户配置）
    return None


def generate_oss_signature(method: str, bucket: str, object_name: str, access_key_secret: str) -> str:
    """生成 OSS 签名"""
    date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
    content_type = 'image/png'
    string_to_sign = f"{method}\n\n{content_type}\n{date}\n/{bucket}/{object_name}"
    
    h = hmac.new(access_key_secret.encode(), string_to_sign.encode(), hashlib.sha1)
    signature = base64.b64encode(h.digest()).decode()
    
    return signature, date


def upload_to_oss(file_path: str) -> Optional[str]:
    """
    上传文件到阿里云 OSS
    
    Args:
        file_path: 本地文件路径
    
    Returns:
        文件 URL（失败返回 None）
    """
    config = get_oss_config()
    
    if not config:
        print("❌ 未配置 OSS 凭证")
        print("请在 ~/.openclaw/openclaw.json 中配置:")
        print('  "skills": {')
        print('    "entries": {')
        print('      "xiaorou": {')
        print('        "env": {')
        print('          "OSS_ACCESS_KEY_ID": "your_key_id",')
        print('          "OSS_ACCESS_KEY_SECRET": "your_key_secret",')
        print('          "OSS_BUCKET": "xiaorou-images",')
        print('          "OSS_REGION": "cn-beijing"')
        print('        }')
        print('      }')
        print('    }')
        print('  }')
        return None
    
    access_key_id = config['access_key_id']
    access_key_secret = config['access_key_secret']
    bucket = config['bucket']
    region = config['region']
    
    # 生成对象名称
    object_name = f"xiaorou/{int(time.time())}_{Path(file_path).name}"
    
    # 生成签名
    signature, date = generate_oss_signature('PUT', bucket, object_name, access_key_secret)
    
    # 上传文件
    endpoint = f"https://{bucket}.oss-{region}.aliyuncs.com/{object_name}"
    
    try:
        with open(file_path, 'rb') as f:
            headers = {
                'Authorization': f'OSS {access_key_id}:{signature}',
                'Date': date,
                'Content-Type': 'image/png'
            }
            
            response = requests.put(endpoint, headers=headers, data=f, timeout=60)
        
        if response.status_code == 200:
            url = f"https://{bucket}.oss-{region}.aliyuncs.com/{object_name}"
            print(f"✅ 上传成功：{url}")
            return url
        
        print(f"❌ 上传失败：{response.status_code} - {response.text[:200]}")
        return None
        
    except Exception as e:
        print(f"❌ 上传异常：{e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 upload_image.py <图片路径>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)
    
    url = upload_to_oss(file_path)
    if url:
        print(f"图片 URL: {url}")
        sys.exit(0)
    else:
        sys.exit(1)
