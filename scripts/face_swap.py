#!/usr/bin/env python3
"""
face_swap.py - 小柔换脸脚本（DashScope 多模态图生图 API）

用法：
  python3 face_swap.py <目标图片路径> [频道] [配文] [target]

示例：
  python3 face_swap.py /tmp/photo.jpg feishu "换好了～你看看喜欢吗 💕"
  python3 face_swap.py /tmp/photo.jpg

功能：
  将目标图片中的人脸替换为小柔的脸，场景、穿搭、姿势、光影 100% 保留。
  输出 JSON 结果到 stdout，供上层 agent 读取并发送图片。

原理：
  使用 wan2.7-image / qwen-image-2.0-pro 的多图输入能力：
  - 图1（主输入）：目标图片 → 提供场景/穿搭/姿势/光影
  - 图2（参考）：小柔头像 → 提供脸部身份特征
  Prompt 精确锁定：只换脸，其他完全不变。
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
import shutil
from pathlib import Path
from typing import Optional, Tuple, List

# 导入统一配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import config

TEMP_DIR = config.get_temp_dir() / 'face_swap'
TEMP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

# 小柔脸部特征描述（用于 prompt 中精确锁定身份）
XIAOROU_FACE_DESC = (
    "脸型为柔和的鹅蛋脸，杏仁形深棕色眼睛自然双眼皮，小巧挺拔的鼻子，"
    "唇形自然饱满淡粉色温柔微笑，自然弧度柔和眉毛，细腻光滑白皙肌肤，"
    "黑色长直发自然垂落，发质柔顺。"
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def validate_config() -> str:
    """验证并加载 API Key"""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
        logger.info("✅ 从环境变量加载 API Key")
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
                logger.info("✅ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise RuntimeError("API Key 未设置，请配置环境变量或 ~/.openclaw/openclaw.json")


def get_image_base64(image_path: Path) -> str:
    """读取图片并转换为 base64 data URI"""
    with open(image_path, 'rb') as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"


def validate_target_image(image_path: str) -> Path:
    """验证目标图片路径"""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"目标图片不存在：{image_path}")
    
    # 安全检查：确保文件在允许的目录内
    allowed_dirs = [
        Path('/home/admin/.openclaw/media/inbound'),
        Path('/tmp/openclaw'),
        config.get_temp_dir(),
    ]
    is_allowed = any(path.resolve().is_relative_to(d.resolve()) for d in allowed_dirs)
    if not is_allowed:
        raise PermissionError(f"文件路径不在允许的范围内：{image_path}")
    
    return path


def validate_xiaorou_face() -> Path:
    """验证小柔头像文件"""
    script_dir = Path(__file__).resolve().parent
    face_path = script_dir.parent / 'assets' / 'default-character.png'
    if not face_path.exists():
        raise FileNotFoundError(f"小柔头像不存在：{face_path}")
    return face_path


def build_face_swap_prompt() -> str:
    """
    构建换脸专用 prompt
    核心原则：只换脸，其他 100% 保留
    """
    return (
        f"【极高优先级 - 必须 100% 遵守】这是一张人脸替换创作任务。\n"
        f"图 1 是目标图片（包含完整场景、人物穿搭、姿势、光影、构图）。\n"
        f"图 2 是小柔的头像（提供脸部身份特征）。\n"
        f"\n"
        f"【脸部身份锁定 — 必须使用图 2 的脸】\n"
        f"将图 1 中人物的脸替换为图 2 中小柔的脸。\n"
        f"必须严格保持小柔的脸部特征：{XIAOROU_FACE_DESC}\n"
        f"\n"
        f"【场景 100% 锁定 — 图 1 的一切必须完全保留】\n"
        f"- 场景环境：完全保留图 1 的背景、建筑、装饰、道具\n"
        f"- 人物穿搭：完全保留图 1 的服装款式、颜色、材质、配饰\n"
        f"- 人物姿态：完全保留图 1 的站姿/坐姿/手部动作/身体角度\n"
        f"- 光线光影：完全保留图 1 的光线方向、色调、明暗氛围\n"
        f"- 拍摄构图：完全保留图 1 的拍摄角度、景深、构图方式\n"
        f"- 其他人物/物体：完全保留图 1 中的所有其他元素\n"
        f"\n"
        f"【融合要求 — 必须自然真实无违和感】\n"
        f"- 换脸后脸部与图 1 的光影自然融合，肤色调与图 1 环境光一致\n"
        f"- 看上去就是小柔本人在这个场景下，无任何违和感\n"
        f"- 清淡妆容，裸妆效果，真实摄影风格\n"
        f"- 8K 超高清，细节丰富，色彩自然"
    )


def get_negative_prompt() -> str:
    """负面提示词 — 告诉模型不要做什么"""
    return (
        "改变场景, 改变背景, 改变穿搭, 改变服装, 改变姿势, 改变姿态, "
        "改变光影, 改变光线, 改变构图, 改变色调, 改变配色, "
        "变形的人脸, 脸部扭曲, 五官位移, 脸部畸形, "
        "deformed face, morphed face, warped face, face distortion, "
        "changed scene, changed outfit, changed pose, changed lighting, changed background, "
        "extra limbs, extra hands, mutated limbs, body distortion"
    )


def generate_single_face_swap(
    model_name: str,
    target_image_path: Path,
    face_reference_path: Path,
    api_key: str,
) -> Tuple[str, Optional[str]]:
    """
    使用指定模型执行单张换脸生成
    
    Returns:
        (model_name, image_url) 或 (model_name, None) 如果失败
    """
    try:
        dashscope.api_key = api_key
        target_base64 = get_image_base64(target_image_path)
        face_base64 = get_image_base64(face_reference_path)
        logger.info(f"🖼️ 换脸模式 - 目标图：{target_image_path.name}，脸部参考：{face_reference_path.name}，模型：{model_name}")
        
        # 模型尺寸参数
        if model_name == 'qwen-image-2.0-pro':
            size_param = '1024*1024'
        else:
            size_param = '1K'
        
        # 构建 content 数组：图1 = 目标图（主输入），图2 = 小柔头像（脸部参考）
        content_items = [
            {'image': target_base64},
            {'image': face_base64},
            {'text': build_face_swap_prompt()},
        ]
        
        payload = {
            'model': model_name,
            'input': {'messages': [{'role': 'user', 'content': content_items}]},
            'parameters': {
                'prompt_extend': False,  # 换脸场景不需要 prompt 扩展
                'watermark': False,
                'n': 1,
                'enable_interleave': False,
                'size': size_param,
                'seed': 42,
                'negative_prompt': get_negative_prompt(),
            }
        }
        
        response = requests.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-DataInspection': '{"input":"disable","output":"disable"}',
            },
            json=payload,
            timeout=180,
        )
        
        result_json = response.json()
        if response.status_code == 200 and result_json.get('output'):
            output = result_json['output']
            if 'choices' in output and len(output['choices']) > 0:
                image_url = output['choices'][0]['message']['content'][0]['image']
                logger.info(f"✅ {model_name} 换脸生成成功")
                return (model_name, image_url)
        
        logger.error(f"❌ {model_name} API 错误：{result_json}")
        return (model_name, None)
        
    except Exception as e:
        logger.error(f"❌ {model_name} 换脸错误：{e}")
        return (model_name, None)


def download_and_save(image_url: str, model_name: str = '') -> Optional[str]:
    """下载生成的图片到本地"""
    try:
        os.makedirs('/tmp/openclaw', exist_ok=True)
        timestamp = int(time.time())
        model_tag = model_name.replace('.', '_').replace('-', '_') if model_name else 'face_swap'
        temp_file = f'/tmp/openclaw/face_swap_{model_tag}_{timestamp}.jpg'
        
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        if os.path.getsize(temp_file) == 0:
            logger.error("下载的图片文件为空")
            os.remove(temp_file)
            return None
        
        # 也保存到固定路径（供后续使用）
        latest_path = config.get_temp_dir() / 'face_swap_latest.jpg'
        shutil.copy2(temp_file, str(latest_path))
        logger.info(f"✓ 已保存换脸图片到：{latest_path}")
        
        return temp_file
        
    except Exception as e:
        logger.error(f"保存图片失败：{e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法：python3 face_swap.py <目标图片路径> [频道] [配文] [target]")
        print("示例：python3 face_swap.py /tmp/photo.jpg feishu \"换好了～你看看喜欢吗 💕\"")
        sys.exit(1)
    
    target_path = sys.argv[1]
    channel = sys.argv[2] if len(sys.argv) > 2 else None
    caption = sys.argv[3] if len(sys.argv) > 3 else "换好了～你看看喜欢吗 💕"
    target_user = sys.argv[4] if len(sys.argv) > 4 else None
    
    try:
        # 1. 验证输入
        target = validate_target_image(target_path)
        face_ref = validate_xiaorou_face()
        api_key = validate_config()
        
        logger.info("✅ 输入验证通过")
        logger.info(f"🎯 目标图：{target}")
        logger.info(f"👤 脸部参考：{face_ref}")
        
        # 2. 执行换脸（双模型尝试，提高成功率）
        models = ['wan2.7-image', 'qwen-image-2.0-pro']
        results = []
        
        for model in models:
            try:
                model_name, image_url = generate_single_face_swap(model, target, face_ref, api_key)
                if image_url:
                    results.append((model_name, image_url))
                else:
                    logger.warning(f"⚠️ {model} 换脸失败")
            except Exception as e:
                logger.warning(f"⚠️ {model} 换脸错误：{e}")
        
        if not results:
            logger.error("❌ 所有模型都失败了")
            output = {"type": "error", "message": "所有模型都失败了"}
            print(json.dumps(output, ensure_ascii=False), flush=True)
            sys.exit(1)
        
        # 3. 保存图片并输出结果
        saved_files = []
        for model_name, image_url in results:
            saved_path = download_and_save(image_url, model_name)
            if saved_path:
                saved_files.append({
                    'model': model_name,
                    'file_path': saved_path,
                })
                logger.info(f"✅ {model_name} 图片已保存：{saved_path}")
        
        if not saved_files:
            logger.error("❌ 所有图片保存失败")
            output = {"type": "error", "message": "所有图片保存失败"}
            print(json.dumps(output, ensure_ascii=False), flush=True)
            sys.exit(1)
        
        # 4. 输出 JSON 供上层 agent 解析和发送
        output = {
            "type": "face_swap_done",
            "success": True,
            "count": len(saved_files),
            "results": saved_files,
            "caption": caption,
            "channel": channel,
            "target": target_user or os.environ.get('AEVIA_TARGET', ''),
        }
        print(json.dumps(output, ensure_ascii=False), flush=True)
        
        logger.info(f"✅ 换脸完成，共生成 {len(saved_files)} 张图片")
        sys.exit(0)
        
    except (FileNotFoundError, PermissionError, RuntimeError) as e:
        logger.error(f"❌ 错误：{e}")
        output = {"type": "error", "message": str(e)}
        print(json.dumps(output, ensure_ascii=False), flush=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 未预期错误：{e}")
        output = {"type": "error", "message": str(e)}
        print(json.dumps(output, ensure_ascii=False), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
