#!/usr/bin/env python3.11
"""selfie_bbox.py - 角色替换生成模块 (YOLO 人脸检测 + 局部重绘)

核心功能:
- 使用 YOLO 模型自动检测参考图人脸位置
- 通过 wan2.7 局部重绘功能精准替换脸部
- 保持参考图的场景/服装/姿势/发型 100% 不变

优势:
- 精准控制：只修改脸部区域，其他部分完全保留
- 肤色统一：在指定区域内生成，更容易控制融合
- 减少意外：避免全图生成导致的其他元素变化
"""

import os
import sys
import json
import base64
import logging
import time
import threading
import requests
import uuid
import mimetypes
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse

# 尝试导入 cv2 (OpenCV)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ 警告：opencv-python 未安装，请运行：pip install opencv-python")

# 导入统一配置
from config import config, ConfigurationError

# ========== 常量定义 ==========
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
MAX_PROMPT_LENGTH = 5000
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))

# 配置日志级别
log_level = config.get_log_level()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# 飞书 token 缓存
_feishu_token: Optional[str] = None
_feishu_token_time: float = 0
_feishu_token_lock = threading.Lock()


# ========== OpenCV Haar Cascade 人脸检测 ==========

def load_face_detection_model() -> Optional[object]:
    """加载 OpenCV Haar Cascade 人脸检测模型"""
    if not CV2_AVAILABLE:
        logger.error("❌ OpenCV 不可用：opencv-python 未安装")
        return None
    
    try:
        logger.info("🔍 加载 OpenCV Haar Cascade 人脸检测模型...")
        # 使用 OpenCV 预训练的 Haar Cascade 人脸检测器
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        
        if face_cascade.empty():
            logger.error("无法加载 Haar Cascade 分类器")
            return None
        
        logger.info("✅ OpenCV Haar Cascade 人脸检测模型加载成功")
        return face_cascade
    except Exception as e:
        logger.error(f"❌ 加载人脸检测模型失败：{e}")
        return None


def detect_face_bbox(image_path: str, face_cascade: object, confidence: float = 0.5) -> Optional[List[int]]:
    """
    检测图片中的人脸边界框 (OpenCV Haar Cascade)
    
    Args:
        image_path: 图片路径
        face_cascade: Haar Cascade 分类器
        confidence: 置信度阈值 (未使用，Haar Cascade 使用 minNeighbors)
    
    Returns:
        [x1, y1, x2, y2] 或 None
    """
    try:
        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            logger.error("无法读取图片")
            return None
        
        img_height, img_width = img.shape[:2]
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 人脸检测
        # scaleFactor: 图像缩放比例
        # minNeighbors: 每个候选框至少需要多少个邻居才能被保留
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        if len(faces) == 0:
            logger.warning("⚠️ 未检测到人脸")
            return None
        
        # 取最大的人脸（最靠近镜头）
        face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = face
        
        x1, y1 = x, y
        x2, y2 = x + w, y + h
        
        logger.info(f"✅ 检测到人脸：[{x1}, {y1}, {x2}, {y2}] (尺寸：{w}x{h})")
        return [x1, y1, x2, y2]
        
    except Exception as e:
        logger.error(f"❌ 人脸检测失败：{e}")
        return None


def expand_bbox(bbox: List[int], img_width: int, img_height: int, expand_ratio: float = 0.2) -> List[int]:
    """
    扩展边界框，确保覆盖完整脸部
    
    Args:
        bbox: [x1, y1, x2, y2]
        img_width: 图片宽度
        img_height: 图片高度
        expand_ratio: 扩展比例 (默认 20%)
    
    Returns:
        扩展后的 bbox
    """
    x1, y1, x2, y2 = bbox
    
    # 计算宽高
    width = x2 - x1
    height = y2 - y1
    
    # 扩展
    expand_x = int(width * expand_ratio)
    expand_y = int(height * expand_ratio)
    
    # 确保不超出图片边界，并转换为 Python int
    new_x1 = int(max(0, x1 - expand_x))
    new_y1 = int(max(0, y1 - expand_y))
    new_x2 = int(min(img_width, x2 + expand_x))
    new_y2 = int(min(img_height, y2 + expand_y))
    
    return [new_x1, new_y1, new_x2, new_y2]


# ========== 图片处理 ==========

def validate_image_file(file_path: str) -> bool:
    """验证图片文件类型"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
        if header[:3] == b'\xff\xd8\xff':  # JPEG
            return True
        if header[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
            return True
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':  # WEBP
            return True
        return False
    except Exception as e:
        logger.debug(f"图片验证失败:{e}")
        return False


def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64 格式"""
    file_size = image_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"图片文件为空:{image_path}")
    if file_size > 20 * 1024 * 1024:  # 20MB
        raise ValueError(f"图片文件过大:{file_size / 1024 / 1024:.2f}MB")
    
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/png'
    
    with open(image_path, 'rb') as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"


def get_image_size(image_path: str) -> Tuple[int, int]:
    """获取图片尺寸"""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except Exception as e:
        logger.warning(f"获取图片尺寸失败：{e}")
        # 尝试用 cv2
        try:
            import cv2
            img = cv2.imread(image_path)
            return (img.shape[1], img.shape[0])
        except:
            return (1024, 1024)  # 默认值


# ========== wan2.7 API 调用 ==========

def validate_config() -> str:
    """验证配置并返回 API Key"""
    try:
        api_key = config.get_api_key()
        logger.debug("✅ API Key 验证通过")
        return api_key
    except ConfigurationError as e:
        logger.error(f"❌ 配置错误:{e}")
        raise


def build_inpaint_prompt() -> str:
    """构建局部重绘提示词"""
    return """【局部重绘指令 - 最高优先级】
这是一张"人脸替换"局部重绘任务：
- **只修改 bbox 框选区域内的人脸**
- **bbox 区域外的所有内容 100% 完全保持不变**
- **使用图 2(小柔) 的脸部特征替换图 1 的 bbox 区域**

【人脸锁定 - 终极权重 5.0】
- **图 2 的脸部特征必须 100% 完整复刻到 bbox 区域**
- **图 2 的五官、脸型、神态必须完全保留，零变形**
- **bbox 区域外的场景/服装/姿势/发型/背景完全不变**
- **生成结果 = 图 1 的原图 (除 bbox 区域) + 图 2 的脸 (bbox 区域)**

【肤色统一 - 最高优先级】
- **脸部、颈部肤色必须 100% 一致，不能有任何色差**
- **颈部与脸部不能有分界线，肤色完全相同**
- **禁止脸部/颈部过白/过黑/过红/过黄/发暗/发灰**

【边缘融合 - 最高优先级】
- **bbox 区域边缘必须自然过渡，不能有分界线**
- **肤色渐变必须平滑，与周围皮肤无缝融合**
- **光影必须与原图一致，不能有突兀感**

【光源一致性】
- **光源方向/强度/色温必须与原图一致**
- **阴影/高光位置必须匹配原图光照**

【无水印 - 绝对禁止】
- **禁止任何形式的水印、logo、文字**
- **画面必须干净纯净**

【质量要求】
- 真实摄影质感，无 AI 感
- 皮肤纹理自然，可见毛孔
- 8K 超高清，专业人像摄影"""


def generate_face_swap_inpaint(
    reference_image_path: Path,
    character_image_path: Path,
    face_bbox: List[int],
    prompt: str,
    api_key: str,
    max_retries: int = 2
) -> Tuple[str, Optional[str]]:
    """
    使用 wan2.7 进行人脸局部重绘替换
    
    Args:
        reference_image_path: 参考图路径
        character_image_path: 小柔头像路径
        face_bbox: 人脸边界框 [x1, y1, x2, y2]
        prompt: 提示词
        api_key: API Key
        max_retries: 最大重试次数
    
    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    model_name = 'wan2.7-image-pro'  # 使用 Pro 版本支持更高质量
    
    for attempt in range(max_retries + 1):
        try:
            reference_base64 = get_image_base64(reference_image_path)
            character_base64 = get_image_base64(character_image_path)
            
            logger.info(f"🎨 局部重绘模式：参考图 + 小柔头像 + bbox (尝试 {attempt + 1}/{max_retries + 1})")
            logger.info(f"📦 Bbox 坐标：{face_bbox}")
            
            # 构建请求
            content = [
                {'image': reference_base64},      # 图 1: 参考图 (基础图)
                {'image': character_base64},      # 图 2: 小柔头像 (提供脸部)
                {'text': prompt}
            ]
            
            payload = {
                'model': model_name,
                'input': {
                    'messages': [{
                        'role': 'user',
                        'content': content
                    }]
                },
                'parameters': {
                    'prompt_extend': False,
                    'watermark': False,
                    'n': 1,
                    'size': '2K',  # 局部重绘最高支持 2K
                    'bbox_list': [[face_bbox], []],  # [[[x1, y1, x2, y2]], []] - 图 1 有 bbox，图 2 无 bbox
                }
            }
            
            response = requests.post(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
                    'X-DashScope-Log': 'disable',
                },
                json=payload,
                timeout=API_TIMEOUT
            )
            
            result_json = response.json()
            
            if response.status_code == 200 and result_json.get('output'):
                output = result_json['output']
                if 'choices' in output and len(output['choices']) > 0:
                    image_url = output['choices'][0]['message']['content'][0]['image']
                    logger.info(f"✅ {model_name} 局部重绘生成成功")
                    return (model_name, image_url)
            
            logger.error(f"❌ {model_name} API 错误:{result_json}")
            
            if attempt < max_retries:
                logger.warning(f"⚠️ {model_name} 重试中...")
                time.sleep(1 * (attempt + 1))
                continue
            
            return (model_name, None)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ {model_name} JSON 解析失败:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
            
        except requests.RequestException as e:
            logger.error(f"❌ {model_name} 请求异常:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)
            
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
            
        except Exception as e:
            logger.error(f"❌ {model_name} 错误:{e}")
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
                continue
            return (model_name, None)


# ========== 飞书消息发送 ==========

def get_feishu_credentials() -> Tuple[Optional[str], Optional[str]]:
    """获取飞书 API 凭证"""
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                openclaw_config = json.load(f)
            app_id = openclaw_config.get('channels', {}).get('feishu', {}).get('appId', '')
            app_secret = openclaw_config.get('channels', {}).get('feishu', {}).get('appSecret', '')
            if app_id and app_secret:
                return app_id, app_secret
        except Exception as e:
            logger.debug(f"读取飞书配置失败:{e}")
    return None, None


def get_feishu_access_token() -> Optional[str]:
    """获取飞书 access_token"""
    global _feishu_token, _feishu_token_time
    
    if _feishu_token and (time.time() - _feishu_token_time) < 7200:
        return _feishu_token
    
    with _feishu_token_lock:
        if _feishu_token and (time.time() - _feishu_token_time) < 7200:
            return _feishu_token
        
        app_id, app_secret = get_feishu_credentials()
        if not app_id or not app_secret:
            return None
        
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        try:
            token_response = requests.post(
                token_url,
                headers={"Content-Type": "application/json"},
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=30
            )
            token_data = token_response.json()
            access_token = token_data.get('tenant_access_token', '')
            if access_token:
                _feishu_token = access_token
                _feishu_token_time = time.time()
                return access_token
        except Exception as e:
            logger.warning(f"获取飞书 access_token 失败:{e}")
    return None


def upload_feishu_image(image_file: str) -> Optional[str]:
    """上传图片到飞书"""
    access_token = get_feishu_access_token()
    if not access_token:
        return None
    
    upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
    with open(image_file, 'rb') as f:
        files = {'image': (os.path.basename(image_file), f, 'image/jpeg')}
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
        logger.info(f"✅ 飞书图片上传成功:{image_key}")
        return image_key
    return None


def send_feishu_image_message(image_key: str, caption: str, receive_id: str, receive_id_type: Optional[str] = None) -> bool:
    """发送飞书原生图片消息"""
    access_token = get_feishu_access_token()
    if not access_token:
        return False
    
    if receive_id_type is None:
        if receive_id.startswith('ou_'):
            receive_id_type = 'open_id'
        elif receive_id.startswith('on_'):
            receive_id_type = 'union_id'
        else:
            return False
    
    message_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    content = json.dumps({"image_key": image_key, "text": caption})
    message_data = {"receive_id": receive_id, "msg_type": "image", "content": content}
    
    response = requests.post(
        message_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=message_data,
        timeout=60
    )
    
    result = response.json()
    return result.get('code') == 0


def send_to_channel(image_url: str, caption: str, channel: str, model_name: str, target: Optional[str] = None) -> bool:
    """发送图片到频道"""
    try:
        logger.info(f"📤 发送到:{channel}")
        temp_dir = config.get_temp_dir()
        temp_file = f'{temp_dir}/selfie_bbox_{uuid.uuid4().hex[:8]}.jpg'
        os.makedirs(str(temp_dir), mode=0o700, exist_ok=True)
        
        # 下载图片
        response = requests.get(image_url, timeout=60)
        if response.status_code == 200:
            with open(temp_file, 'wb') as f:
                f.write(response.content)
        else:
            logger.error(f"下载图片失败:{response.status_code}")
            return False
        
        # 飞书使用原生图片消息
        if channel == 'feishu':
            send_target = target or os.environ.get('AEVIA_TARGET', '')
            if not send_target:
                send_target = config.get_feishu_target()
            if not send_target:
                logger.error("未配置飞书目标用户")
                return False
            
            image_key = upload_feishu_image(temp_file)
            if image_key:
                if send_feishu_image_message(image_key, caption, send_target):
                    logger.info("✓ 飞书原生图片发送成功")
                    return True
        else:
            send_target = target or os.environ.get('AEVIA_TARGET', '')
            cmd_args = ['openclaw', 'message', 'send', '--channel', channel, '--target', send_target, '--message', caption, '--media', temp_file]
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        
        return False
        
    except Exception as e:
        logger.error(f"发送异常:{e}")
        return False


# ========== 主流程 ==========

def generate_face_swap_bbox(reference_image_path: str, caption: str = "这是 bbox 局部重绘生成的~", channel: Optional[str] = None, target: Optional[str] = None) -> bool:
    """
    BBOX 局部重绘模式：YOLO 人脸检测 + wan2.7 局部重绘
    
    Args:
        reference_image_path: 参考图路径
        caption: 发送消息的配文
        channel: 发送频道
        target: 发送目标
    
    Returns:
        是否成功
    """
    try:
        api_key = validate_config()
        logger.info(f"✅ API Key 已加载")
        
        # 验证参考图
        ref_path = Path(reference_image_path)
        if not ref_path.exists():
            logger.error(f"参考图不存在:{reference_image_path}")
            return False
        logger.info("✅ 参考图验证通过")
        
        # 加载小柔头像
        script_dir = Path(__file__).resolve().parent
        character_path = script_dir.parent / 'assets/default-character.png'
        if not character_path.exists():
            logger.error(f"头像文件不存在:{character_path}")
            return False
        logger.info("✅ 头像文件验证通过")
        
        # 加载 MediaPipe 人脸检测模型
        logger.info("🔍 加载 MediaPipe 人脸检测模型...")
        face_model = load_face_detection_model()
        if not face_model:
            logger.error("❌ MediaPipe 模型加载失败")
            return False
        
        # 检测人脸 bbox
        logger.info("🔍 检测人脸...")
        face_bbox = detect_face_bbox(str(ref_path), face_model, confidence=0.5)
        
        if not face_bbox:
            logger.error("❌ 未检测到人脸")
            return False
        
        # 获取图片尺寸并扩展 bbox
        img_width, img_height = get_image_size(str(ref_path))
        expanded_bbox = expand_bbox(face_bbox, img_width, img_height, expand_ratio=0.2)
        logger.info(f"📦 扩展后 bbox: {expanded_bbox}")
        
        # 构建局部重绘 prompt
        prompt = build_inpaint_prompt()
        logger.info("🎨 BBOX 局部重绘模式")
        
        # 调用 wan2.7 局部重绘 API
        logger.info("🚀 wan2.7-image-pro 局部重绘生成中...")
        model_name, image_url = generate_face_swap_inpaint(
            ref_path,
            character_path,
            expanded_bbox,
            prompt,
            api_key
        )
        
        if not image_url:
            logger.error("❌ 生成失败")
            return False
        
        # 发送生成的图片
        if channel:
            effective_target = target or os.environ.get('AEVIA_TARGET')
            if send_to_channel(image_url, caption, channel, model_name, effective_target):
                logger.info("✅ 发送成功")
                return True
            else:
                logger.error("❌ 发送失败")
                return False
        
        return True
        
    except (ConfigurationError, FileNotFoundError) as e:
        logger.error(f"❌ 错误:{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 错误:{e}")
        return False


if __name__ == "__main__":
    import subprocess
    
    LOCK_FILE = str(config.get_temp_dir() / "selfie_bbox_task.lock")
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  BBOX 局部重绘：python3 selfie_bbox.py --bbox <参考图路径> [频道] [配文] [target]")
        sys.exit(1)
    
    if sys.argv[1] == '--bbox' and len(sys.argv) >= 3:
        reference_image = sys.argv[2]
        if not os.path.exists(reference_image):
            logger.error(f"参考图不存在:{reference_image}")
            sys.exit(1)
        
        channel = sys.argv[3] if len(sys.argv) > 3 else None
        caption = sys.argv[4] if len(sys.argv) > 4 else "这是 bbox 局部重绘生成的~"
        target = sys.argv[5] if len(sys.argv) > 5 else None
        
        success = generate_face_swap_bbox(reference_image, caption, channel, target)
        sys.exit(0 if success else 1)
    else:
        print("用法:")
        print("  BBOX 局部重绘：python3 selfie_bbox.py --bbox <参考图路径> [频道] [配文] [target]")
        sys.exit(1)
