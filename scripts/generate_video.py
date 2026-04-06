#!/usr/bin/env python3
"""generate_video.py - 小柔统一视频生成工具（优化版）

整合所有视频生成功能：
1. 图生视频（本地图片 → 视频）
2. 图片 + 音频 → 视频

支持模型：
- wan2.7-i2v（推荐，最新）
- wan2.6-i2v

优化内容：
- 使用统一配置模块
- 添加重试机制
- 使用连接池
- 改进错误处理
- 安全临时文件处理
"""

import os
import sys
import time
import re
import requests
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# 导入统一配置
from config import config, ConfigurationError

# ============ 配置初始化 ============

# 使用配置模块
TEMP_DIR = config.get_temp_dir() / 'videos'
TEMP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
POLL_INTERVAL = int(os.environ.get('XIAOROU_POLL_INTERVAL', '10'))
MAX_WAIT = int(os.environ.get('XIAOROU_MAX_WAIT', '600'))
# 从环境变量读取目标平台，支持多平台
DEFAULT_TARGET = os.environ.get('AEVIA_TARGET', '')
DEFAULT_CHANNEL = os.environ.get('AEVIA_CHANNEL', 'feishu')

# 创建 requests session（连接池）
session = requests.Session()

# ============ 安全工具函数 ============

def safe_log(message: str) -> str:
    """
    日志脱敏处理，移除敏感信息
    
    Args:
        message: 原始日志消息
    
    Returns:
        脱敏后的消息
    """
    # 脱敏 API Key
    message = re.sub(r'sk-[a-zA-Z0-9]{20,}', 'sk-****REDACTED****', message)
    # 脱敏 OSS URL（包含签名）
    message = re.sub(r'Signature=[a-zA-Z0-9%]+', 'Signature=****REDACTED****', message)
    return message


class SafeLogger:
    """安全日志包装器，自动脱敏敏感信息"""
    
    def __init__(self, logger):
        self._logger = logger
    
    def info(self, msg, *args, **kwargs):
        self._logger.info(safe_log(msg), *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self._logger.warning(safe_log(msg), *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self._logger.error(safe_log(msg), *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(safe_log(msg), *args, **kwargs)


# 使用安全日志包装器
logger = SafeLogger(logging.getLogger(__name__))


# ============ 重试装饰器 ============

def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(f"⚠️ 尝试 {attempt}/{max_attempts} 失败：{e}，{delay}秒后重试...")
                        time.sleep(delay)
                        delay *= 2  # 指数退避
                    else:
                        logger.error(f"❌ 尝试 {max_attempts}/{max_attempts} 失败")
            raise last_exception
        return wrapper
    return decorator


# ============ 工具函数 ============

@retry_on_failure(max_attempts=3, delay=1.0)
def upload_to_dashscope(file_path: str, api_key: str, model_name: str = "wan2.7-i2v") -> Optional[str]:
    """
    使用 DashScope 官方上传 API 获取临时文件 URL
    
    参考：https://help.aliyun.com/zh/model-studio/get-temporary-file-url
    有效期：48 小时
    
    Args:
        file_path: 本地文件路径
        api_key: DashScope API Key
        model_name: 模型名称
    
    Returns:
        oss:// URL（失败返回 None）
    """
    try:
        # 1. 获取上传凭证
        logger.info(f"📤 正在获取上传凭证...")
        policy_url = "https://dashscope.aliyuncs.com/api/v1/uploads"
        params = {"action": "getPolicy", "model": model_name}
        headers = {"Authorization": f"Bearer {api_key}"}
        
        response = session.get(policy_url, headers=headers, params=params, timeout=30, verify=True)
        if response.status_code != 200:
            logger.error(f"❌ 获取上传凭证失败：{response.text[:200]}")
            return None
        
        policy_data = response.json().get('data', {})
        if not policy_data:
            logger.error(f"❌ 未获取到上传凭证：{response.json()}")
            return None
        
        logger.info(f"✅ 上传凭证获取成功")
        
        # 2. 上传文件到 OSS（P2 修复 - 文件名二次验证）
        file_name = Path(file_path).name
        # 验证文件名安全性
        if not file_name or '..' in file_name or file_name.startswith('/'):
            logger.error(f"❌ 无效的文件名：{file_name}")
            return None
        key = f"{policy_data['upload_dir']}/{file_name}"
        
        logger.info(f"📤 正在上传文件...")
        with open(file_path, 'rb') as f:
            files = {
                'OSSAccessKeyId': (None, policy_data['oss_access_key_id']),
                'Signature': (None, policy_data['signature']),
                'policy': (None, policy_data['policy']),
                'x-oss-object-acl': (None, policy_data['x_oss_object_acl']),
                'x-oss-forbid-overwrite': (None, policy_data['x_oss_forbid_overwrite']),
                'key': (None, key),
                'success_action_status': (None, '200'),
                'file': (file_name, f)
            }
            
            response = session.post(policy_data['upload_host'], files=files, timeout=60, verify=True)
        
        if response.status_code != 200:
            logger.error(f"❌ 上传失败：{response.text[:200]}")
            return None
        
        # 返回 oss:// URL
        oss_url = f"oss://{key}"
        logger.info(f"✅ 文件上传成功：{oss_url}")
        logger.info(f"⏰ 有效期：48 小时")
        
        return oss_url
        
    except requests.exceptions.Timeout:
        logger.error("❌ 上传超时，请检查网络连接")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ 连接错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 上传异常：{type(e).__name__}: {e}")
        return None


@retry_on_failure(max_attempts=3, delay=2.0)
def generate_video(
    prompt: str,
    img_url: Optional[str] = None,
    audio_url: Optional[str] = None,
    resolution: str = "720P",
    duration: int = 5,
    model: str = "wan2.7-i2v",
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    使用 wan2.7-i2v / wan2.6-i2v 生成视频
    
    Args:
        prompt: 视频描述提示词
        img_url: 图片 URL（oss:// 或 https://）
        audio_url: 音频 URL（可选，oss:// 或 https://）
        resolution: 分辨率 (720P/1080P)
        duration: 视频时长 (秒)
        model: 模型名称 (wan2.7-i2v / wan2.6-i2v)
        api_key: DashScope API Key
    
    Returns:
        (成功标志，视频 URL 或错误信息)
    """
    if not api_key:
        api_key = config.get_api_key()
    
    logger.info(f"🎬 开始生成视频...")
    logger.info(f"  模型：{model}")
    logger.info(f"  提示词：{prompt[:100]}...")
    logger.info(f"  图片 URL: {img_url or '无'}")
    logger.info(f"  音频 URL: {audio_url or '无'}")
    logger.info(f"  分辨率：{resolution}")
    logger.info(f"  时长：{duration}秒")
    
    # 构建请求体
    if model == "wan2.7-i2v":
        # wan2.7-i2v 新格式：使用 media 数组
        input_data = {"prompt": prompt, "media": []}
        
        if img_url:
            input_data["media"].append({"type": "first_frame", "url": img_url})
        
        if audio_url:
            input_data["media"].append({"type": "driving_audio", "url": audio_url})
        
        payload = {
            "model": model,
            "input": input_data,
            "parameters": {
                "resolution": resolution,
                "prompt_extend": True,
                "duration": duration,
                "watermark": False  # 关闭水印
            }
        }
    else:
        # wan2.6-i2v 旧格式：使用 img_url
        input_data = {"prompt": prompt}
        
        if img_url:
            input_data["img_url"] = img_url
        
        if audio_url:
            input_data["audio_url"] = audio_url
        
        payload = {
            "model": model,
            "input": input_data,
            "parameters": {
                "resolution": resolution,
                "prompt_extend": True,
                "duration": duration,
                "shot_type": "multi"
            }
        }
    
    # 提交异步任务
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-DashScope-Async': 'enable'
        }
        
        # 如果是 oss:// URL，需要添加 OSS 资源解析 header
        has_oss = (img_url and img_url.startswith('oss://')) or (audio_url and audio_url.startswith('oss://'))
        if has_oss:
            headers['X-DashScope-OssResourceResolve'] = 'enable'
        
        response = session.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis',
            headers=headers,
            json=payload,
            timeout=60,
            verify=True
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
        
    except requests.exceptions.Timeout:
        logger.error("❌ API 请求超时")
        return (False, "API 请求超时，请检查网络连接")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ 连接错误：{e}")
        return (False, f"无法连接 API 服务：{str(e)}")
    except Exception as e:
        logger.error(f"❌ 请求失败：{type(e).__name__}: {e}")
        return (False, f"请求失败：{type(e).__name__}")


def poll_task_status(task_id: str, api_key: str) -> Tuple[bool, str]:
    """
    轮询任务状态直到完成（使用指数退避）
    
    Args:
        task_id: 任务 ID
        api_key: DashScope API Key
    
    Returns:
        (成功标志，视频 URL 或错误信息)
    """
    logger.info(f"⏳ 等待视频生成完成...")
    
    start_time = time.time()
    poll_interval = POLL_INTERVAL  # 初始轮询间隔
    
    while time.time() - start_time < MAX_WAIT:
        try:
            response = session.get(
                f'https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=30,
                verify=True
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
                # 指数退避：每次增加 50%，最大 30 秒
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 30)
                continue
            
            else:
                logger.warning(f"⚠️ 未知状态：{task_status}")
                time.sleep(poll_interval)
                continue
                
        except requests.exceptions.Timeout:
            logger.error("❌ 轮询超时")
            continue
        except Exception as e:
            logger.error(f"❌ 轮询失败：{type(e).__name__}: {e}")
            continue
    
    logger.error(f"❌ 等待超时（{MAX_WAIT}秒）")
    return (False, f"等待超时（{MAX_WAIT}秒）")


def download_video(video_url: str, output_path: str) -> bool:
    """
    下载视频到本地（原子操作，避免不完整文件）
    
    Args:
        video_url: 视频 URL
        output_path: 输出文件路径
    
    Returns:
        是否成功
    """
    logger.info(f"📥 下载视频到：{output_path}")
    
    temp_path = str(output_path) + '.tmp'
    
    try:
        response = session.get(video_url, timeout=300, stream=True, verify=True)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 原子操作：重命名临时文件
        os.replace(temp_path, output_path)
        
        logger.info(f"✅ 视频已保存：{output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 下载失败：{type(e).__name__}: {e}")
        # 清理不完整文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def send_to_channel(video_path: str, caption: str, channel: str = 'feishu', target: str = None) -> bool:
    """
    发送视频到指定平台
    
    Args:
        video_path: 视频文件路径
        caption: 消息配文
        channel: 目标平台 (feishu/telegram/discord/whatsapp)
        target: 目标用户 ID（默认从环境变量读取）
    
    Returns:
        bool: 是否成功
    """
    # 如果没有指定 target，从环境变量读取
    if target is None:
        target = os.environ.get('AEVIA_TARGET', '')
    
    logger.info(f"📤 发送视频到 {channel}...")
    
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', channel,
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
        
    except subprocess.TimeoutExpired:
        logger.error("❌ 发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ 发送异常：{type(e).__name__}: {e}")
        return False


# ============ 主流程 ============

def image_to_video(
    image_path: str,
    prompt: str,
    audio_path: Optional[str] = None,
    resolution: str = "720P",
    duration: int = 5,
    model: str = "wan2.7-i2v",
    channel: str = None,
    target: str = None,
    send_message: bool = True
) -> Optional[str]:
    """
    图生视频完整流程（支持图片 + 音频，支持多平台）
    
    Args:
        image_path: 本地图片路径
        prompt: 视频描述提示词
        audio_path: 本地音频路径（可选）
        resolution: 分辨率
        duration: 视频时长
        model: 模型名称
        channel: 目标平台（默认从环境变量读取）
        target: 目标用户（默认从环境变量读取）
        send_message: 是否发送到目标平台
    
    Returns:
        视频文件路径（失败返回 None）
    """
    # 从环境变量读取默认值
    if channel is None:
        channel = DEFAULT_CHANNEL
    if target is None:
        target = DEFAULT_TARGET
    logger.info("=" * 60)
    logger.info("🎬 小柔图生视频流程启动")
    logger.info("=" * 60)
    
    api_key = config.get_api_key()
    timestamp = int(time.time())
    
    # 步骤 1: 验证图片
    if not os.path.exists(image_path):
        logger.error(f"❌ 图片不存在：{image_path}")
        return None
    
    logger.info(f"📸 步骤 1: 验证图片...")
    logger.info(f"  图片路径：{image_path}")
    logger.info(f"✅ 图片验证通过")
    
    # 步骤 2: 上传图片到 OSS
    logger.info(f"📤 步骤 2: 上传图片到 DashScope OSS...")
    img_url = upload_to_dashscope(image_path, api_key, model)
    
    if not img_url:
        logger.error("❌ 流程终止：图片上传失败")
        return None
    
    # 步骤 3: 上传音频（如果有）
    audio_url = None
    if audio_path and os.path.exists(audio_path):
        logger.info(f"🎵 步骤 3: 上传音频到 DashScope OSS...")
        audio_url = upload_to_dashscope(audio_path, api_key, model)
        if not audio_url:
            logger.warning("⚠️ 音频上传失败，继续无音频视频流程...")
    
    # 步骤 4: 生成视频
    success, video_result = generate_video(
        prompt=prompt,
        img_url=img_url,
        audio_url=audio_url,
        resolution=resolution,
        duration=duration,
        model=model,
        api_key=api_key
    )
    
    if not success:
        logger.error(f"❌ 流程终止：视频生成失败 - {video_result}")
        return None
    
    # 步骤 5: 下载视频
    video_path = TEMP_DIR / f"video_{timestamp}.mp4"
    if not download_video(video_result, str(video_path)):
        logger.error("❌ 流程终止：视频下载失败")
        return None
    
    # 步骤 6: 发送到飞书
    if send_message:
        caption = f"🎬 小柔生成的视频～\n{prompt[:50]}..."
        if not send_to_feishu(str(video_path), caption, target):
            logger.error("❌ 流程终止：发送失败")
            return None
    
    logger.info("=" * 60)
    logger.info("✅ 视频生成流程完成！")
    logger.info("=" * 60)
    
    return str(video_path)


# ============ 命令行入口 ============

if __name__ == "__main__":
    import argparse
    
    # 配置日志级别
    log_level = config.get_log_level()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(levelname)s: %(message)s',
        stream=sys.stderr
    )
    
    parser = argparse.ArgumentParser(
        description='小柔统一视频生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:

1. 图生视频（推荐 wan2.7-i2v）:
   python3 generate_video.py --image photo.jpg --prompt "描述文字" --model wan2.7-i2v

2. 图片 + 音频 → 视频:
   python3 generate_video.py --image photo.jpg --audio audio.mp3 --prompt "描述文字"

3. 自定义时长和分辨率:
   python3 generate_video.py --image photo.jpg --prompt "描述文字" --duration 10 --resolution 1080P

4. 不自动发送（只生成）:
   python3 generate_video.py --image photo.jpg --prompt "描述文字" --no-send
        """
    )
    
    parser.add_argument('--image', type=str, required=True, help='输入图片路径')
    parser.add_argument('--prompt', type=str, required=True, help='视频描述提示词')
    parser.add_argument('--audio', type=str, help='输入音频路径（可选）')
    parser.add_argument('--model', type=str, default='wan2.7-i2v', help='模型名称 (wan2.7-i2v / wan2.6-i2v)')
    parser.add_argument('--resolution', type=str, default='720P', help='分辨率 (720P/1080P)')
    parser.add_argument('--duration', type=int, default=5, help='视频时长（秒）')
    parser.add_argument('--channel', type=str, default=None, help='目标平台（默认从环境变量读取）')
    parser.add_argument('--target', type=str, default=None, help='目标用户（默认从环境变量读取）')
    parser.add_argument('--no-send', action='store_true', help='不自动发送')
    
    args = parser.parse_args()
    
    try:
        video_path = image_to_video(
            image_path=args.image,
            prompt=args.prompt,
            audio_path=args.audio,
            resolution=args.resolution,
            duration=args.duration,
            model=args.model,
            channel=args.channel,
            target=args.target,
            send_message=not args.no_send
        )
        
        if video_path:
            print(f"\n✅ 视频生成成功！")
            print(f"   本地路径：{video_path}")
            sys.exit(0)
        else:
            print(f"\n❌ 视频生成失败")
            sys.exit(1)
    except ConfigurationError as e:
        print(f"\n❌ 配置错误：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未知错误：{type(e).__name__}: {e}")
        sys.exit(1)
