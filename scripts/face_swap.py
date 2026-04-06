#!/usr/bin/env python3
"""face_swap.py - 换脸生成模块 (4 模型并发)

使用 4 个模型并发生成换脸图片：
- wan2.7-image
- wan2.7-image-pro
- qwen-image-2.0
- qwen-image-2.0-pro

统一 Prompt：我想让图 1 的脸换成图 2 的脸部特征，其他图 1 的部分全部不变，最后要自然、无 AI 感、去掉水印。
"""

import dashscope
import os
import sys
import json
import base64
import logging
import re
import time
import requests
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入统一配置
from config import config, ConfigurationError

# 使用配置模块
TEMP_DIR = config.get_temp_dir() / 'face_swaps'
TEMP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
MAX_INPUT_LENGTH = 500
DEFAULT_IMAGE_SIZE = "1K"
# 超时配置
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))
IMAGE_DOWNLOAD_TIMEOUT = int(os.environ.get('XIAOROU_IMAGE_DOWNLOAD_TIMEOUT', '30'))

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# 4 个换脸模型
FACE_SWAP_MODELS = [
    'wan2.7-image',
    'wan2.7-image-pro',
    'qwen-image-2.0',
    'qwen-image-2.0-pro'
]

# 统一换脸 Prompt
FACE_SWAP_PROMPT = "我想让图 1 的脸换成图 2 的脸部特征，其他图 1 的部分全部不变，最后要自然、无 AI 感、去掉水印。"

# 小柔默认头像路径
XIAOROU_DEFAULT_AVATAR = Path(__file__).parent.parent / 'assets' / 'default-character.png'


class FaceSwapError(Exception):
    """换脸生成异常"""
    pass


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
                cfg = json.load(f)
            api_key = cfg.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            if not api_key:
                api_key = cfg.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
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


def download_image(url: str, save_path: Path) -> bool:
    """下载图片到本地"""
    try:
        response = requests.get(url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        
        # 验证文件类型
        mime_type, _ = mimetypes.guess_type(save_path)
        if mime_type not in ['image/jpeg', 'image/png', 'image/webp']:
            logger.error(f"文件类型不正确：{mime_type}")
            return False
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"✓ 图片已保存：{save_path}")
        return True
    except Exception as e:
        logger.error(f"下载图片失败：{e}")
        return False


def generate_face_swap(
    model_name: str,
    image1_path: str,
    image2_path: str,
    api_key: str,
    output_dir: Path
) -> Tuple[bool, str, Optional[Path]]:
    """
    使用指定模型生成换脸图片
    
    Args:
        model_name: 模型名称
        image1_path: 图 1 路径（用户提供的图片）
        image2_path: 图 2 路径（小柔默认头像）
        api_key: DashScope API Key
        output_dir: 输出目录
    
    Returns:
        (成功标志，消息，输出图片路径)
    """
    import dashscope
    from dashscope import ImageSynthesis
    
    dashscope.api_key = api_key
    timestamp = int(time.time())
    
    try:
        # 读取两张图片的 base64
        with open(image1_path, 'rb') as f:
            image1_data = base64.b64encode(f.read()).decode('utf-8')
        with open(image2_path, 'rb') as f:
            image2_data = base64.b64encode(f.read()).decode('utf-8')
        
        logger.info(f" 正在使用 {model_name} 生成换脸图片...")
        
        # 构建多模态对话请求
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": f"data:image/jpeg;base64,{image1_data}"
                    },
                    {
                        "image": f"data:image/jpeg;base64,{image2_data}"
                    },
                    {
                        "text": FACE_SWAP_PROMPT
                    }
                ]
            }
        ]
        
        # 调用模型（使用多模态 API）
        import requests
        
        # 不同模型对 size 参数格式要求不同
        if 'qwen-image' in model_name:
            size_param = '1024*1024'  # qwen-image 系列使用分辨率格式
        else:
            size_param = DEFAULT_IMAGE_SIZE  # wan2.7 系列使用 1K/2K 格式
        
        payload = {
            'model': model_name,
            'input': {'messages': messages},
            'parameters': {'prompt_extend': True, 'size': size_param, 'n': 1}
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}'
            },
            json=payload,
            timeout=120
        )
        
        result_json = response.json()
        
        if response.status_code == 200 and result_json.get('output'):
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                choice = output['choices'][0]
                if choice.get('message') and choice['message'].get('content'):
                    # 提取生成的图片 URL
                    for item in choice['message']['content']:
                        if isinstance(item, dict) and item.get('image'):
                            image_url = item['image']
                            
                            # 下载生成的图片
                            output_filename = f"face_swap_{model_name.replace('.', '_')}_{timestamp}.jpg"
                            output_path = output_dir / output_filename
                            
                            img_response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
                            img_response.raise_for_status()
                            
                            with open(output_path, 'wb') as f:
                                f.write(img_response.content)
                            
                            logger.info(f"✅ {model_name} 生成成功：{output_path}")
                            return (True, f"{model_name} 生成成功", output_path)
            
            logger.error(f"{model_name}: 响应格式异常 - {result_json}")
            return (False, f"{model_name}: 响应格式异常", None)
        else:
            error_msg = f"{model_name}: API 调用失败 - {response.status_code} {result_json}"
            logger.error(error_msg)
            return (False, error_msg, None)
            
    except Exception as e:
        error_msg = f"{model_name}: {type(e).__name__}: {e}"
        logger.error(error_msg)
        return (False, error_msg, None)


def face_swap(
    image1_path: str,
    image2_path: Optional[str] = None,
    models: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    执行换脸生成（4 模型并发）
    
    Args:
        image1_path: 图 1 路径（用户提供的图片）
        image2_path: 图 2 路径（可选，默认使用小柔默认头像）
        models: 使用的模型列表（可选，默认使用全部 4 个模型）
    
    Returns:
        包含生成结果的字典
    """
    # 验证配置
    api_key = validate_config()
    
    # 验证图 1
    if not Path(image1_path).exists():
        raise FaceSwapError(f"图 1 文件不存在：{image1_path}")
    
    # 验证图 2（使用默认头像）
    if image2_path is None:
        if not XIAOROU_DEFAULT_AVATAR.exists():
            raise FaceSwapError(f"小柔默认头像不存在：{XIAOROU_DEFAULT_AVATAR}")
        image2_path = str(XIAOROU_DEFAULT_AVATAR)
        logger.info(f"使用小柔默认头像：{image2_path}")
    elif not Path(image2_path).exists():
        raise FaceSwapError(f"图 2 文件不存在：{image2_path}")
    
    # 使用指定模型或默认全部
    if models is None:
        models = FACE_SWAP_MODELS
    
    logger.info(f"🚀 开始换脸生成，使用 {len(models)} 个模型并发处理...")
    logger.info(f"  图 1: {image1_path}")
    logger.info(f"  图 2: {image2_path}")
    logger.info(f"  模型：{', '.join(models)}")
    
    # 创建输出目录
    timestamp = int(time.time())
    output_dir = TEMP_DIR / f"face_swap_{timestamp}"
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    
    # 并发生成
    results = {
        'success': [],
        'failed': [],
        'output_dir': output_dir,
        'images': {}
    }
    
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        future_to_model = {
            executor.submit(
                generate_face_swap,
                model_name,
                image1_path,
                image2_path,
                api_key,
                output_dir
            ): model_name
            for model_name in models
        }
        
        for future in as_completed(future_to_model):
            model_name = future_to_model[future]
            try:
                success, message, output_path = future.result()
                if success and output_path:
                    results['success'].append(model_name)
                    results['images'][model_name] = output_path
                    logger.info(f"✅ {model_name}: {message}")
                else:
                    results['failed'].append({'model': model_name, 'error': message})
                    logger.error(f"❌ {model_name}: {message}")
            except Exception as e:
                results['failed'].append({'model': model_name, 'error': str(e)})
                logger.error(f"❌ {model_name}: 异常 - {e}")
    
    # 汇总结果
    total = len(models)
    success_count = len(results['success'])
    failed_count = len(results['failed'])
    
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 换脸生成完成")
    logger.info(f"  总计：{total} 个模型")
    logger.info(f"  成功：{success_count} 个")
    logger.info(f"  失败：{failed_count} 个")
    logger.info(f"  输出目录：{output_dir}")
    logger.info(f"{'='*50}")
    
    return results


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='小柔 AI 换脸生成工具')
    parser.add_argument('image1', help='图 1 路径（用户提供的图片）')
    parser.add_argument('--image2', '-i2', help='图 2 路径（可选，默认使用小柔默认头像）')
    parser.add_argument('--models', '-m', nargs='+', choices=FACE_SWAP_MODELS, help='指定使用的模型')
    parser.add_argument('--output', '-o', help='输出目录')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    # 从配置文件读取默认 target（如果是飞书平台）
    default_channel = os.environ.get('AEVIA_CHANNEL', 'feishu')
    default_target = os.environ.get('AEVIA_TARGET', '')
    if not default_target and default_channel == 'feishu':
        default_target = config.get_feishu_target()
    
    parser.add_argument('--channel', '-c', choices=['feishu', 'telegram', 'discord', 'whatsapp'], 
                       default=default_channel, help='发送频道')
    parser.add_argument('--target', '-t', default=default_target, 
                       help='发送目标（open_id 或 chat_id）')
    parser.add_argument('--caption', default='换脸完成～看看效果怎么样？', help='发送消息的配文')
    parser.add_argument('--auto-send', action='store_true', default=True, 
                       help='生成完成后自动发送（默认启用）')
    parser.add_argument('--no-send', action='store_false', dest='auto_send', 
                       help='只生成不发送')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        results = face_swap(args.image1, args.image2, args.models)
        
        # 输出结果
        print("\n" + "="*50)
        print("📊 换脸生成结果")
        print("="*50)
        
        if results['success']:
            print(f"\n✅ 成功 ({len(results['success'])}/{len(FACE_SWAP_MODELS)}):")
            for model in results['success']:
                print(f"  • {model}: {results['images'][model]}")
        
        if results['failed']:
            print(f"\n❌ 失败 ({len(results['failed'])}/{len(FACE_SWAP_MODELS)}):")
            for item in results['failed']:
                print(f"  • {item['model']}: {item['error']}")
        
        print(f"\n📁 输出目录：{results['output_dir']}")
        print("="*50)
        
        # 如果启用自动发送，发送图片
        if args.auto_send and results['success']:
            # 尝试从环境变量或配置读取 target
            send_target = args.target or os.environ.get('AEVIA_TARGET', '')
            
            # 如果没有配置 target，尝试从默认配置读取
            if not send_target and args.channel == 'feishu':
                send_target = config.get_feishu_target()
            
            if not send_target:
                print("\n⚠️  警告：未指定发送目标，跳过发送")
                print("请使用 --target 指定目标，或配置 AEVIA_TARGET 环境变量")
            else:
                print(f"\n📤 正在发送到 {args.channel} (target: {send_target})...")
                import subprocess
                import shutil
                
                caption = args.caption
            
            # 模型名称映射（带 emoji）
            model_display_map = {
                'wan2.7-image': '🎨【万相 2.7】',
                'wan2.7-image-pro': '🎨【万相 2.7 Pro】',
                'qwen-image-2.0': '🖼️【千问 2.0】',
                'qwen-image-2.0-pro': '🖼️【千问 2.0 Pro】'
            }
            
            # 保存最新换脸结果到固定路径（供其他功能使用）
            latest_path = config.get_temp_dir() / 'face_swap_latest.jpg'
            
            for i, model_name in enumerate(results['success']):
                image_path = results['images'][model_name]
                model_emoji = model_display_map.get(model_name, f'📷【{model_name}】')
                
                # 第一个图片附带完整文字说明
                if i == 0:
                    full_caption = f"🎭 换脸生图完成！\n\n{model_emoji}\n{caption}\n\n共生成 {len(results['success'])} 张"
                else:
                    full_caption = f"{model_emoji} 换脸生图"
                
                print(f"  发送：{image_path} ({model_emoji})")
                
                # 使用 openclaw message send 发送（所有平台统一）
                cmd = [
                    'openclaw', 'message', 'send',
                    '--channel', args.channel,
                    '--target', send_target,
                    '--message', full_caption,
                    '--media', str(image_path)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    print(f"    ✅ 发送成功")
                    
                    # 保存最新结果到固定路径（原子操作）
                    if i == 0:
                        try:
                            temp_dst = str(latest_path) + '.tmp'
                            shutil.copy2(image_path, temp_dst)
                            os.replace(temp_dst, str(latest_path))
                            print(f"    ✓ 已保存最新结果到：{latest_path}")
                        except Exception as e:
                            print(f"    ⚠️ 保存失败：{e}")
                else:
                    print(f"    ❌ 发送失败：{result.stderr}")
            
            print("\n✅ 换脸生图全部完成！")
        
        # 返回成功状态
        sys.exit(0 if results['success'] else 1)
        
    except (ConfigurationError, FaceSwapError) as e:
        logger.error(f"❌ 错误：{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断")
        sys.exit(130)


if __name__ == '__main__':
    main()
