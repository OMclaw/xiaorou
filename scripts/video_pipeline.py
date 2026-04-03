#!/usr/bin/env python3
"""video_pipeline.py - 视频生成完整流程

完整流程：
1. 参考图生图（生成图片）
2. TTS 语音生成（生成音频）
3. 视频合成（图片 + 音频 → 视频）
4. 发送到飞书

使用模型：
- 图片：wan2.7-image / qwen-image-2.0-pro
- 语音：CosyVoice-v3-flash
- 视频：wan2.6-i2v
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
    """验证 API Key"""
    if DASHSCOPE_API_KEY and re.match(r'^sk-[a-zA-Z0-9]{20,}$', DASHSCOPE_API_KEY):
        return DASHSCOPE_API_KEY
    
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
        if api_key:
            return api_key
    
    raise Exception("API Key 未设置")


def upload_to_oss(file_path: str) -> Optional[str]:
    """
    上传文件到飞书获取公网 URL
    
    使用飞书图片上传 API 获取 image_key，然后构造公网 URL
    """
    try:
        # 读取飞书凭证
        config_file = os.path.expanduser('~/.openclaw/openclaw.json')
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        app_id = config.get('channels', {}).get('feishu', {}).get('appId', '')
        app_secret = config.get('channels', {}).get('feishu', {}).get('appSecret', '')
        
        if not app_id or not app_secret:
            logger.error("❌ 未配置飞书凭证")
            return None
        
        # 1. 获取 access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        token_response = requests.post(
            token_url,
            headers={"Content-Type": "application/json"},
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=30
        )
        token_data = token_response.json()
        access_token = token_data.get('tenant_access_token', '')
        
        if not access_token:
            logger.error("❌ 获取 access_token 失败")
            return None
        
        # 2. 上传图片
        upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
        with open(file_path, 'rb') as f:
            files = {'image': (os.path.basename(file_path), f, 'image/jpeg')}
            data = {'image_type': 'message'}
            upload_response = requests.post(
                upload_url,
                headers={"Authorization": f"Bearer {access_token}"},
                files=files,
                data=data,
                timeout=60
            )
        
        upload_data = upload_response.json()
        if upload_data.get('code') == 0:
            image_key = upload_data.get('data', {}).get('image_key', '')
            # 构造飞书图片 URL（临时方案：使用飞书 CDN）
            img_url = f"https://open.feishu.cn/open-apis/im/v1/images/{image_key}"
            logger.info(f"✅ 图片上传成功：{image_key}")
            return img_url
        
        logger.error(f"❌ 飞书上传失败：{upload_data}")
        return None
        
    except Exception as e:
        logger.error(f"❌ 上传异常：{e}")
        return None


# ============ 步骤 1: 生成图片 ============

def generate_image(reference_image: str, prompt: str) -> Optional[str]:
    """
    直接使用参考图片（不重新生成）
    
    Args:
        reference_image: 参考图片路径
        prompt: 生成提示（用于日志）
    
    Returns:
        图片路径
    """
    logger.info(f"📸 步骤 1: 使用参考图片...")
    logger.info(f"  图片路径：{reference_image}")
    
    # 直接使用参考图片，不重新生成
    if os.path.exists(reference_image):
        logger.info(f"✅ 图片验证通过")
        return reference_image
    
    logger.error(f"❌ 图片不存在：{reference_image}")
    return None


# ============ 步骤 2: 生成语音 ============

def generate_tts(text: str, voice: str = "longxiaoxia") -> Optional[str]:
    """
    使用 CosyVoice 生成语音
    
    Args:
        text: 文本内容
        voice: 音色名称
    
    Returns:
        音频文件路径（失败返回 None）
    """
    logger.info(f"🎙️ 步骤 2: 生成语音...")
    
    tts_script = Path(__file__).parent / 'tts.py'
    output_file = TEMP_DIR / f"audio_{int(time.time())}.mp3"
    
    cmd = [
        'python3.11', str(tts_script),
        '--voice', voice,
        '--text', text,
        '--output', str(output_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and output_file.exists():
            logger.info(f"✅ 语音生成成功：{output_file}")
            return str(output_file)
        
        logger.warning(f"⚠️ 语音生成失败（跳过音频）: {result.stderr[:200]}")
        return None  # 返回 None 继续流程
        
    except Exception as e:
        logger.warning(f"⚠️ 语音生成异常（跳过音频）: {e}")
        return None


# ============ 步骤 3: 生成视频 ============

def generate_video(
    prompt: str,
    img_url: str,
    audio_url: Optional[str] = None,
    resolution: str = "720P",
    duration: int = 5,
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    使用 wan2.6-i2v 生成视频
    
    Args:
        prompt: 视频描述
        img_url: 图片 URL
        audio_url: 音频 URL（可选）
        resolution: 分辨率
        duration: 视频时长
        api_key: API Key
    
    Returns:
        (成功标志，视频 URL 或错误信息)
    """
    if not api_key:
        api_key = validate_config()
    
    logger.info(f"🎬 步骤 3: 生成视频...")
    logger.info(f"  模型：wan2.6-i2v")
    logger.info(f"  提示词：{prompt[:100]}...")
    logger.info(f"  图片 URL: {img_url}")
    logger.info(f"  音频 URL: {audio_url or '无'}")
    logger.info(f"  时长：{duration}秒")
    
    # 构建请求体
    input_data = {
        "prompt": prompt,
        "img_url": img_url
    }
    
    if audio_url:
        input_data["audio_url"] = audio_url
    
    parameters = {
        "resolution": resolution,
        "prompt_extend": True,
        "duration": duration,
        "audio": bool(audio_url),
        "shot_type": "multi"
    }
    
    payload = {
        "model": "wan2.6-i2v",
        "input": input_data,
        "parameters": parameters
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
    """轮询任务状态"""
    logger.info(f"⏳ 等待视频生成完成...")
    
    start_time = time.time()
    poll_interval = 10
    
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
                continue
                
        except Exception as e:
            logger.error(f"❌ 轮询失败：{e}")
            continue
    
    logger.error(f"❌ 等待超时（{max_wait}秒）")
    return (False, f"等待超时")


# ============ 步骤 4: 下载视频 ============

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


# ============ 步骤 5: 发送到飞书 ============

def send_to_feishu(video_path: str, caption: str, target: str = FEISHU_TARGET) -> bool:
    """发送视频到飞书"""
    logger.info(f"📤 发送视频到飞书...")
    
    # 使用 openclaw message 命令发送
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', target,
        '--message', caption,
        '--media', video_path
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


# ============ 完整流程 ============

def generate_video_pipeline(
    reference_image: str,
    scene_prompt: str,
    tts_text: str,
    video_prompt: str,
    duration: int = 5,
    target: str = FEISHU_TARGET
) -> bool:
    """
    完整视频生成流程
    
    Args:
        reference_image: 参考图片路径
        scene_prompt: 图片生成提示词
        tts_text: TTS 文本内容
        video_prompt: 视频生成提示词
        duration: 视频时长（秒）
        target: 飞书目标用户
    
    Returns:
        是否成功
    """
    logger.info("=" * 60)
    logger.info("🎬 小柔视频生成流程启动")
    logger.info("=" * 60)
    
    api_key = validate_config()
    timestamp = int(time.time())
    
    # 步骤 1: 生成图片
    image_path = generate_image(reference_image, scene_prompt)
    if not image_path:
        logger.error("❌ 流程终止：图片生成失败")
        return False
    
    # 步骤 2: 生成语音（可选）
    audio_path = generate_tts(tts_text)
    if not audio_path:
        logger.warning("⚠️ 语音生成失败，继续无音频视频流程...")
    
    # 步骤 3: 上传图片到 OSS
    logger.info(f"📤 上传文件到 OSS...")
    img_url = upload_to_oss(image_path)
    audio_url = upload_to_oss(audio_path)
    
    if not img_url:
        logger.error("❌ 流程终止：图片上传失败")
        return False
    
    # 步骤 4: 生成视频
    success, video_result = generate_video(
        prompt=video_prompt,
        img_url=img_url,
        audio_url=audio_url,
        duration=duration,
        api_key=api_key
    )
    
    if not success:
        logger.error(f"❌ 流程终止：视频生成失败 - {video_result}")
        return False
    
    video_url = video_result
    
    # 步骤 5: 下载视频
    video_path = TEMP_DIR / f"video_{timestamp}.mp4"
    if not download_video(video_url, str(video_path)):
        logger.error("❌ 流程终止：视频下载失败")
        return False
    
    # 步骤 6: 发送到飞书
    caption = f"🎬 小柔生成的视频～\n{video_prompt[:50]}..."
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
    
    parser = argparse.ArgumentParser(description='小柔视频生成完整流程')
    parser.add_argument('--reference', type=str, required=True, help='参考图片路径')
    parser.add_argument('--scene-prompt', type=str, required=True, help='图片生成提示词')
    parser.add_argument('--tts-text', type=str, required=True, help='TTS 文本内容')
    parser.add_argument('--video-prompt', type=str, required=True, help='视频生成提示词')
    parser.add_argument('--duration', type=int, default=5, help='视频时长（秒）')
    parser.add_argument('--target', type=str, default=FEISHU_TARGET, help='飞书目标用户')
    
    args = parser.parse_args()
    
    success = generate_video_pipeline(
        reference_image=args.reference,
        scene_prompt=args.scene_prompt,
        tts_text=args.tts_text,
        video_prompt=args.video_prompt,
        duration=args.duration,
        target=args.target
    )
    
    sys.exit(0 if success else 1)
