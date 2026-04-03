#!/usr/bin/env python3
"""image_to_video.py - 图生视频模块

直接使用用户提供的图片 + 文字描述生成视频
支持：
1. 本地图片 → 上传到阿里云 OSS → 生成视频
2. 图片 + 文字 → 视频
3. 发送到飞书

使用模型：wan2.6-i2v
"""

import os
import sys
import json
import time
import requests
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


# ============ 配置 ============

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
FEISHU_TARGET = os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')

# 临时文件目录
TEMP_DIR = Path('/tmp/xiaorou_video')
TEMP_DIR.mkdir(exist_ok=True)


# ============ 工具函数 ============

def validate_config() -> str:
    """验证并加载 API Key"""
    if DASHSCOPE_API_KEY and re.match(r'^sk-[a-zA-Z0-9]{20,}$', DASHSCOPE_API_KEY):
        logger.info("✓ 从环境变量加载 API Key")
        return DASHSCOPE_API_KEY
    
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
        if api_key:
            logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
            return api_key
    
    raise Exception("API Key 未设置")


def upload_to_aliyun_oss(file_path: str) -> Optional[str]:
    """
    上传文件到阿里云 OSS 获取公网 URL
    
    使用 oss2 SDK
    """
    try:
        import oss2
        
        # 从配置文件读取 OSS 凭证
        config_file = os.path.expanduser('~/.openclaw/openclaw.json')
        if not os.path.exists(config_file):
            logger.error("❌ 配置文件不存在")
            return None
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # 尝试从多种位置读取 OSS 配置
        oss_config = None
        
        # 位置 1: skills.entries.xiaorou.env
        if not oss_config:
            oss_config = config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {})
            if oss_config.get('OSS_ACCESS_KEY_ID'):
                oss_config = {
                    'access_key_id': oss_config['OSS_ACCESS_KEY_ID'],
                    'access_key_secret': oss_config['OSS_ACCESS_KEY_SECRET'],
                    'bucket': oss_config.get('OSS_BUCKET', 'xiaorou-images'),
                    'region': oss_config.get('OSS_REGION', 'cn-beijing')
                }
            else:
                oss_config = None
        
        # 位置 2: 独立的 oss 配置
        if not oss_config:
            oss_config = config.get('oss', {})
            if not oss_config.get('access_key_id'):
                oss_config = None
        
        if not oss_config:
            logger.error("❌ 未配置 OSS 凭证")
            logger.info("请在 ~/.openclaw/openclaw.json 中配置 OSS 信息")
            return None
        
        access_key_id = oss_config['access_key_id']
        access_key_secret = oss_config['access_key_secret']
        bucket_name = oss_config['bucket']
        region = oss_config['region']
        
        # 创建 Auth 和 Bucket 对象
        auth = oss2.Auth(access_key_id, access_key_secret)
        endpoint = f"oss-{region}.aliyuncs.com"
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        
        # 生成对象名称
        object_name = f"xiaorou/{int(time.time())}_{Path(file_path).name}"
        
        # 上传文件
        logger.info(f"📤 正在上传图片到 OSS...")
        result = bucket.put_object_from_file(object_name, file_path)
        
        if result.status == 200:
            img_url = f"https://{bucket_name}.{endpoint}/{object_name}"
            logger.info(f"✅ 图片上传成功：{img_url}")
            return img_url
        
        logger.error(f"❌ OSS 上传失败：{result.status}")
        return None
        
    except ImportError:
        logger.error("❌ 未安装 oss2 库，请运行：pip3 install oss2")
        return None
    except Exception as e:
        logger.error(f"❌ OSS 上传异常：{e}")
        return None


def upload_to_aliyun_dashscope(file_path: str, api_key: str) -> Optional[str]:
    """
    使用阿里云 DashScope 的文件上传接口
    
    注意：DashScope 没有公开的文件上传 API，需要使用 OSS
    """
    # 尝试使用 dashscope 的上传接口
    try:
        upload_url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/files/upload'
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'image/png')}
            response = requests.post(
                upload_url,
                headers={'Authorization': f'Bearer {api_key}'},
                files=files,
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            file_url = result.get('output', {}).get('url', '')
            if file_url:
                logger.info(f"✅ 文件上传成功：{file_url}")
                return file_url
        
        logger.warning(f"⚠️ DashScope 上传失败：{response.text[:200]}")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ DashScope 上传异常：{e}")
        return None


def generate_video(
    prompt: str,
    img_url: str,
    resolution: str = "720P",
    duration: int = 5,
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    使用 wan2.6-i2v 生成视频
    
    Args:
        prompt: 视频描述提示词
        img_url: 图片 URL（必须公网可访问）
        resolution: 分辨率 (720P/1080P)
        duration: 视频时长 (秒)
        api_key: DashScope API Key
    
    Returns:
        (成功标志，视频 URL 或错误信息)
    """
    if not api_key:
        api_key = validate_config()
    
    logger.info(f"🎬 开始生成视频...")
    logger.info(f"  模型：wan2.6-i2v")
    logger.info(f"  提示词：{prompt[:100]}...")
    logger.info(f"  图片 URL: {img_url}")
    logger.info(f"  分辨率：{resolution}")
    logger.info(f"  时长：{duration}秒")
    
    # 构建请求体
    payload = {
        "model": "wan2.6-i2v",
        "input": {
            "prompt": prompt,
            "img_url": img_url
        },
        "parameters": {
            "resolution": resolution,
            "prompt_extend": True,
            "duration": duration,
            "shot_type": "multi"
        }
    }
    
    # 提交异步任务
    try:
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            },
            json=payload,
            timeout=60
        )
        
        result = response.json()
        
        if response.status_code != 200:
            logger.error(f"❌ 提交任务失败：{result}")
            return (False, f"提交任务失败：{result}")
        
        task_id = result.get('output', {}).get('task_id', '')
        if not task_id:
            logger.error(f"❌ 未获取到 task_id: {result}")
            return (False, f"未获取到 task_id: {result}")
        
        logger.info(f"✅ 任务提交成功，task_id: {task_id}")
        
        # 轮询任务状态
        return poll_task_status(task_id, api_key)
        
    except Exception as e:
        logger.error(f"❌ 请求失败：{e}")
        return (False, f"请求失败：{e}")


def poll_task_status(task_id: str, api_key: str, max_wait: int = 600) -> Tuple[bool, str]:
    """
    轮询任务状态直到完成
    
    Args:
        task_id: 任务 ID
        api_key: DashScope API Key
        max_wait: 最大等待时间（秒）
    
    Returns:
        (成功标志，视频 URL 或错误信息)
    """
    logger.info(f"⏳ 等待视频生成完成...")
    
    start_time = time.time()
    poll_interval = 10  # 每 10 秒轮询一次
    
    while time.time() - start_time < max_wait:
        time.sleep(poll_interval)
        
        try:
            response = requests.get(
                f'https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=30
            )
            
            result = response.json()
            task_status = result.get('output', {}).get('task_status', 'UNKNOWN')
            
            logger.info(f"  任务状态：{task_status}")
            
            if task_status == 'SUCCEEDED':
                video_url = result.get('output', {}).get('video_url', '')
                logger.info(f"✅ 视频生成成功！")
                logger.info(f"  视频 URL: {video_url}")
                return (True, video_url)
            
            elif task_status == 'FAILED':
                error_message = result.get('output', {}).get('message', '未知错误')
                logger.error(f"❌ 视频生成失败：{error_message}")
                return (False, f"视频生成失败：{error_message}")
            
            elif task_status in ['PENDING', 'RUNNING']:
                continue
            
            else:
                logger.warning(f"⚠️ 未知状态：{task_status}")
                continue
                
        except Exception as e:
            logger.error(f"❌ 轮询失败：{e}")
            continue
    
    logger.error(f"❌ 等待超时（{max_wait}秒）")
    return (False, f"等待超时（{max_wait}秒）")


def download_video(video_url: str, output_path: str) -> bool:
    """下载视频到本地"""
    logger.info(f"📥 下载视频到：{output_path}")
    
    try:
        response = requests.get(video_url, timeout=300)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"✅ 视频已保存：{output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 下载失败：{e}")
        return False


def send_to_feishu(video_path: str, caption: str, target: str = FEISHU_TARGET) -> bool:
    """发送视频到飞书"""
    logger.info(f"📤 发送视频到飞书...")
    
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', target,
        '--message', caption,
        '--media', str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"✅ 视频已发送到飞书")
            return True
        
        logger.error(f"❌ 发送失败：{result.stderr}")
        return False
        
    except Exception as e:
        logger.error(f"❌ 发送异常：{e}")
        return False


# ============ 主流程 ============

def image_to_video(
    image_path: str,
    prompt: str,
    resolution: str = "720P",
    duration: int = 5,
    target: str = FEISHU_TARGET
) -> bool:
    """
    图生视频完整流程
    
    Args:
        image_path: 本地图片路径
        prompt: 视频描述提示词
        resolution: 分辨率
        duration: 视频时长
        target: 飞书目标用户
    
    Returns:
        是否成功
    """
    logger.info("=" * 60)
    logger.info("🎬 小柔图生视频流程启动")
    logger.info("=" * 60)
    
    api_key = validate_config()
    timestamp = int(time.time())
    
    # 步骤 1: 验证图片
    if not os.path.exists(image_path):
        logger.error(f"❌ 图片不存在：{image_path}")
        return False
    
    logger.info(f"📸 步骤 1: 验证图片...")
    logger.info(f"  图片路径：{image_path}")
    logger.info(f"✅ 图片验证通过")
    
    # 步骤 2: 上传图片获取公网 URL
    logger.info(f"📤 步骤 2: 上传图片到阿里云 OSS...")
    
    img_url = upload_to_aliyun_oss(image_path)
    
    if not img_url:
        logger.error("❌ 流程终止：图片上传失败")
        logger.info("💡 请确保在 ~/.openclaw/openclaw.json 中配置了 OSS 凭证")
        return False
    
    # 步骤 3: 生成视频
    success, video_result = generate_video(
        prompt=prompt,
        img_url=img_url,
        resolution=resolution,
        duration=duration,
        api_key=api_key
    )
    
    if not success:
        logger.error(f"❌ 流程终止：视频生成失败 - {video_result}")
        return False
    
    video_url = video_result
    
    # 步骤 4: 下载视频
    video_path = TEMP_DIR / f"video_{timestamp}.mp4"
    if not download_video(video_url, str(video_path)):
        logger.error("❌ 流程终止：视频下载失败")
        return False
    
    # 步骤 5: 发送到飞书
    caption = f"🎬 小柔生成的视频～\n{prompt[:50]}..."
    if not send_to_feishu(str(video_path), caption, target):
        logger.error("❌ 流程终止：发送失败")
        return False
    
    logger.info("=" * 60)
    logger.info("✅ 视频生成流程完成！")
    logger.info("=" * 60)
    
    return True


# ============ 命令行入口 ============

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='小柔图生视频工具')
    parser.add_argument('--image', type=str, required=True, help='输入图片路径')
    parser.add_argument('--prompt', type=str, required=True, help='视频描述提示词')
    parser.add_argument('--resolution', type=str, default='720P', help='分辨率 (720P/1080P)')
    parser.add_argument('--duration', type=int, default=5, help='视频时长（秒）')
    parser.add_argument('--target', type=str, default=FEISHU_TARGET, help='飞书目标用户')
    
    args = parser.parse_args()
    
    success = image_to_video(
        image_path=args.image,
        prompt=args.prompt,
        resolution=args.resolution,
        duration=args.duration,
        target=args.target
    )
    
    sys.exit(0 if success else 1)
