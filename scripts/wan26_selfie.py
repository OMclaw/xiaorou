#!/usr/bin/env python3
"""
wan26_selfie.py - Wan2.6-image API caller for selfie generation
Extracted from selfie.sh to avoid "Argument list too long" error

API Key 优先级（从高到低）：
1. 命令行参数 --api-key
2. 环境变量 DASHSCOPE_API_KEY
3. OpenClaw 配置文件 (~/.openclaw/openclaw.json)
"""

import requests
import base64
import json
import sys
import os
from pathlib import Path

def load_openclaw_api_key():
    """
    从 OpenClaw 配置文件加载 API Key
    
    Returns:
        str or None: API Key，如果找不到则返回 None
    """
    config_paths = [
        Path.home() / '.openclaw' / 'openclaw.json',
        Path.home() / '.config' / 'openclaw' / 'openclaw.json',
    ]
    
    for config_path in config_paths:
        if not config_path.exists():
            continue
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 尝试 dashscope 提供商
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey')
            if api_key and api_key != '$api-key':
                return api_key
            
            # 尝试 dashscope-us 提供商
            api_key = config.get('models', {}).get('providers', {}).get('dashscope-us', {}).get('apiKey')
            if api_key and api_key != '$api-key':
                return api_key
        
        except (json.JSONDecodeError, KeyError, IOError):
            continue
    
    return None

def get_api_key(api_key_arg=None):
    """
    获取 API Key，按优先级返回第一个可用的
    
    优先级：
    1. 命令行参数 --api-key
    2. 环境变量 DASHSCOPE_API_KEY
    3. OpenClaw 配置文件
    
    Args:
        api_key_arg: 命令行参数传入的 API Key（可选）
    
    Returns:
        str: API Key
    
    Raises:
        ValueError: 如果找不到任何可用的 API Key
    """
    # 优先级 1: 命令行参数
    if api_key_arg:
        return api_key_arg
    
    # 优先级 2: 环境变量
    env_key = os.environ.get('DASHSCOPE_API_KEY')
    if env_key and env_key != 'sk-your-api-key-here':
        return env_key
    
    # 优先级 3: OpenClaw 配置文件
    config_key = load_openclaw_api_key()
    if config_key:
        return config_key
    
    raise ValueError(
        "No API Key found. Please set it via:\n"
        "  1. Command line: --api-key sk-xxx\n"
        "  2. Environment: export DASHSCOPE_API_KEY=sk-xxx\n"
        "  3. OpenClaw config: ~/.openclaw/openclaw.json"
    )

def generate_selfie(image_path, prompt, api_key, timeout=120):
    """
    Generate selfie using Wan2.6-image API
    
    Args:
        image_path: Path to reference image
        prompt: Text prompt for generation
        api_key: Dashscope API key
        timeout: Request timeout in seconds (default: 120)
    
    Returns:
        dict: API response JSON
    """
    try:
        # Read and encode image
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Build payload
        payload = {
            'model': 'wan2.6-image',
            'input': {
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'image': f'data:image/png;base64,{img_data}'},
                        {'text': prompt}
                    ]
                }]
            },
            'parameters': {'size': '1024*1024', 'n': 1}
        }
        
        # Call API
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=timeout
        )
        
        return response.json()
    
    except requests.exceptions.Timeout:
        return {'code': 'Timeout', 'message': f'Request timed out after {timeout} seconds'}
    except requests.exceptions.RequestException as e:
        return {'code': 'RequestError', 'message': str(e)}
    except FileNotFoundError:
        return {'code': 'FileNotFound', 'message': f'Image file not found: {image_path}'}
    except Exception as e:
        return {'code': 'Error', 'message': str(e)}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Wan2.6-image API caller for selfie generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
API Key 优先级（从高到低）：
  1. --api-key 参数
  2. DASHSCOPE_API_KEY 环境变量
  3. OpenClaw 配置文件 (~/.openclaw/openclaw.json)

示例：
  # 使用 OpenClaw 配置的 API Key
  python3 wan26_selfie.py image.png "prompt"
  
  # 使用环境变量
  export DASHSCOPE_API_KEY=sk-xxx
  python3 wan26_selfie.py image.png "prompt"
  
  # 使用命令行参数
  python3 wan26_selfie.py image.png "prompt" --api-key sk-xxx
'''
    )
    
    parser.add_argument('image_path', help='Path to reference image')
    parser.add_argument('prompt', help='Text prompt for generation')
    parser.add_argument('--api-key', '-k', default=None, help='Dashscope API key (optional)')
    parser.add_argument('--timeout', '-t', type=int, default=120, help='Request timeout in seconds (default: 120)')
    
    args = parser.parse_args()
    
    # 获取 API Key（兼容 OpenClaw 配置）
    try:
        api_key = get_api_key(args.api_key)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    result = generate_selfie(args.image_path, args.prompt, api_key, args.timeout)
    print(json.dumps(result))
    
    # Exit with error code if API returned an error
    if 'code' in result and result['code'] not in [None, '']:
        sys.exit(1)
    if 'error' in result:
        sys.exit(1)

if __name__ == '__main__':
    main()
