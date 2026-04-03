#!/usr/bin/env python3
"""video_generator.py - 视频生成模块 (wan2.6-i2v)

支持：
1. 图片 + 文字 → 视频
2. 图片 + 文字 + 音频 → 视频

使用阿里云 wan2.6-i2v 模型
"""

import os
import sys
import json
import time
import requests
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception): pass
class VideoGenerationError(Exception): pass


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
                config = json.load(f)
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            if not api_key:
                api_key = config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
            if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
                logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise ConfigurationError("API Key 未设置，请配置环境变量或 ~/.openclaw/openclaw.json")


def upload_to_oss(file_path: str, api_key: str, bucket: str = "dashscope", region: str = "cn-shanghai") -> str:
    """
    上传文件到阿里云 OSS，返回 URL
    
    Args:
        file_path: 本地文件路径
        api_key: DashScope API Key
        bucket: OSS bucket 名称
        region: OSS 区域
    
    Returns:
        文件 URL
    """
    import oss2
    from oss2 import SizedFileAdapter, determine_part_size
    from oss2.models import PartInfo
    
    # 从 API Key 推导 OSS 凭证（简化处理）
    # 实际应该使用独立的 OSS 凭证
    auth = oss2.Auth('LTAI5t...', '...')  # 需要配置
    endpoint = f"{region}.aliyuncs.com"
    
    try:
        bucket_obj = oss2.Bucket(auth, endpoint, bucket)
        
        # 生成对象名称
        object_name = f"xiaorou/{int(time.time())}_{os.path.basename(file_path)}"
        
        # 上传文件
        with open(file_path, 'rb') as f:
            bucket_obj.put_object(object_name, f)
        
        # 返回 URL
        url = f"https://{bucket}.{endpoint}/{object_name}"
        logger.info(f"✅ 文件已上传到 OSS: {url}")
        return url
        
    except Exception as e:
        logger.error(f"❌ OSS 上传失败：{e}")
        return None


def generate_video(
    prompt: str,
    img_url: Optional[str] = None,
    audio_url: Optional[str] = None,
    resolution: str = "720P",
    duration: int = 10,
    enable_audio: bool = True,
    shot_type: str = "multi",
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    使用 wan2.6-i2v 生成视频
    
    Args:
        prompt: 视频描述提示词
        img_url: 输入图片 URL（可选）
        audio_url: 音频 URL（可选）
        resolution: 分辨率 (720P/1080P)
        duration: 视频时长 (秒)
        enable_audio: 是否启用音频
        shot_type: 镜头类型 (multi/single)
        api_key: DashScope API Key
    
    Returns:
        (成功标志，结果 URL 或错误信息)
    """
    if not api_key:
        api_key = validate_config()
    
    # 构建请求体
    input_data = {
        "prompt": prompt
    }
    
    if img_url:
        input_data["img_url"] = img_url
    
    if audio_url and enable_audio:
        input_data["audio_url"] = audio_url
    
    parameters = {
        "resolution": resolution,
        "prompt_extend": True,
        "duration": duration,
        "audio": enable_audio,
        "shot_type": shot_type
    }
    
    payload = {
        "model": "wan2.6-i2v",
        "input": input_data,
        "parameters": parameters
    }
    
    logger.info(f"🎬 开始生成视频...")
    logger.info(f"  模型：wan2.6-i2v")
    logger.info(f"  提示词：{prompt[:100]}...")
    logger.info(f"  分辨率：{resolution}")
    logger.info(f"  时长：{duration}秒")
    
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
        (成功标志，结果 URL 或错误信息)
    """
    logger.info(f"⏳ 等待视频生成完成...")
    
    start_time = time.time()
    poll_interval = 10  # 每 10 秒轮询一次
    
    while time.time() - start_time < max_wait:
        time.sleep(poll_interval)
        
        try:
            response = requests.get(
                f'https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}',
                headers={
                    'Authorization': f'Bearer {api_key}'
                },
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


def generate_video_from_reference(
    reference_image_path: str,
    prompt: str,
    output_path: Optional[str] = None,
    resolution: str = "720P",
    duration: int = 10,
    enable_audio: bool = False,
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    从参考图片生成视频
    
    Args:
        reference_image_path: 参考图片路径
        prompt: 视频描述提示词
        output_path: 输出文件路径（可选）
        resolution: 分辨率
        duration: 视频时长
        enable_audio: 是否启用音频
        api_key: DashScope API Key
    
    Returns:
        (成功标志，结果 URL 或错误信息)
    """
    if not api_key:
        api_key = validate_config()
    
    # 检查图片是否存在
    if not os.path.exists(reference_image_path):
        return (False, f"图片不存在：{reference_image_path}")
    
    # 上传图片获取 URL（简化处理，实际需要上传到 OSS）
    # 这里假设图片已经可以通过 URL 访问
    img_url = f"file://{os.path.abspath(reference_image_path)}"
    
    logger.info(f"📸 使用参考图片：{reference_image_path}")
    
    # 生成视频
    success, result = generate_video(
        prompt=prompt,
        img_url=img_url,
        resolution=resolution,
        duration=duration,
        enable_audio=enable_audio,
        api_key=api_key
    )
    
    if success and output_path:
        # 下载视频到本地
        logger.info(f"📥 下载视频到：{output_path}")
        try:
            video_response = requests.get(result, timeout=300)
            with open(output_path, 'wb') as f:
                f.write(video_response.content)
            logger.info(f"✅ 视频已保存到：{output_path}")
        except Exception as e:
            logger.warning(f"⚠️ 下载视频失败：{e}")
    
    return (success, result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  图片 + 文字 → 视频:")
        print("    python3 video_generator.py --img <图片路径> --prompt \"描述文字\" [--output <输出路径>]")
        print("")
        print("  纯文字 → 视频:")
        print("    python3 video_generator.py --prompt \"描述文字\" [--output <输出路径>]")
        print("")
        print("参数:")
        print("  --img        输入图片路径")
        print("  --prompt     视频描述提示词")
        print("  --output     输出视频路径")
        print("  --resolution 分辨率 (720P/1080P，默认 720P)")
        print("  --duration   视频时长 (秒，默认 10)")
        print("  --audio      是否启用音频 (true/false，默认 false)")
        sys.exit(1)
    
    # 解析参数
    import argparse
    parser = argparse.ArgumentParser(description='视频生成工具')
    parser.add_argument('--img', type=str, help='输入图片路径')
    parser.add_argument('--prompt', type=str, required=True, help='视频描述提示词')
    parser.add_argument('--output', type=str, help='输出视频路径')
    parser.add_argument('--resolution', type=str, default='720P', help='分辨率')
    parser.add_argument('--duration', type=int, default=10, help='视频时长')
    parser.add_argument('--audio', type=str, default='false', help='是否启用音频')
    
    args = parser.parse_args()
    
    # 生成视频
    if args.img:
        success, result = generate_video_from_reference(
            reference_image_path=args.img,
            prompt=args.prompt,
            output_path=args.output,
            resolution=args.resolution,
            duration=args.duration,
            enable_audio=(args.audio.lower() == 'true')
        )
    else:
        success, result = generate_video(
            prompt=args.prompt,
            resolution=args.resolution,
            duration=args.duration,
            enable_audio=(args.audio.lower() == 'true')
        )
    
    if success:
        print(f"\n✅ 视频生成成功！")
        print(f"   URL: {result}")
        if args.output:
            print(f"   本地路径：{args.output}")
        sys.exit(0)
    else:
        print(f"\n❌ 视频生成失败：{result}")
        sys.exit(1)
