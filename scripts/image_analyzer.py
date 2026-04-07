#!/usr/bin/env python3
"""image_analyzer.py - 参考图分析模块 (使用 qwen3.5-plus 视觉能力)

分析参考图，提取场景、姿势、服装、光线等描述，用于后续图生图。
"""

from dashscope import MultiModalConversation
import os
import sys
import json
import base64
import logging
import re
from pathlib import Path
from typing import Optional

# 导入统一配置
from config import config, ConfigurationError


# 超时配置（P1 修复）
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class ImageAnalysisError(Exception):
    """图片分析异常"""
    pass


# P2-3 修复：路径安全检查函数（P2-5 修复：使用 config 统一目录列表）
def _is_path_allowed(file_path: str) -> bool:
    """检查文件路径是否在允许的目录列表内"""
    try:
        resolved = Path(file_path).resolve()
        return any(
            resolved.is_relative_to(allowed.resolve())
            for allowed in config.ALLOWED_IMAGE_DIRS
        )
    except Exception:
        return False


def get_image_base64(image_path: str) -> str:
    """读取图片并转换为 base64"""
    # 检查文件大小（限制 10MB）（P3-2 修复：添加空文件检查）
    file_size = os.path.getsize(image_path)
    if file_size == 0:
        raise ImageAnalysisError(f"图片文件为空：{image_path}")
    if file_size > 10 * 1024 * 1024:
        raise ImageAnalysisError(f"图片文件过大：{file_size / 1024 / 1024:.2f}MB（限制 10MB）")
    
    import mimetypes
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/jpeg'
    
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f"data:{mime_type};base64,{image_data}"


def _call_multimodal_api(image_base64: str, analysis_prompt: str, api_key: str, model: str = 'qwen3.5-plus') -> str:
    """
    调用多模态 API 分析图片（公共函数，避免代码重复）
    
    Args:
        image_base64: base64 编码的图片
        analysis_prompt: 分析 prompt
        api_key: DashScope API Key
        model: 模型名称（默认 qwen3.5-plus）
    
    Returns:
        API 返回的分析结果
    """
    messages = [{
        'role': 'user',
        'content': [
            {'image': image_base64},
            {'text': analysis_prompt}
        ]
    }]
    
    response = MultiModalConversation.call(
        model=model,
        messages=messages,
        api_key=api_key,
        timeout=API_TIMEOUT  # P1-2 修复：传入超时参数
    )
    
    if response.status_code == 200 and response.output:
        output = response.output
        if output.choices and len(output.choices) > 0:
            choice = output.choices[0]
            if choice.message and choice.message.content:
                content = choice.message.content
                # 安全解析：防御 API 返回非预期格式
                if isinstance(content, list) and len(content) > 0:
                    item = content[0]
                    if isinstance(item, dict) and 'text' in item:
                        return item['text']
                # 如果返回的是其他类型，转为字符串
                logger.warning(f"⚠️ API 返回非文本格式：{type(content)}")
                return str(content)
    
    raise ImageAnalysisError(f"API 响应格式异常（status={response.status_code}）")


def analyze_image(image_path: str, api_key: str) -> str:
    """
    使用 qwen3.5-plus 分析参考图，提取场景、姿势、服装、光线等描述
    
    Args:
        image_path: 图片路径
        api_key: DashScope API Key
    
    Returns:
        详细的图片描述 prompt
    """
    try:
        image_base64 = get_image_base64(image_path)
    except Exception as e:
        raise ImageAnalysisError(f"读取图片失败：{e}")
    
    # 构建分析 prompt - 提取场景、姿势、服装、光线等（完全忽略人脸）
    analysis_prompt = """请对这张图片进行特征提取，**完全忽略人脸、五官、面部特征、发型**，只提取以下内容：

1. **背景环境**：场景、光线、色调、氛围
2. **人物姿态**：动作、站姿/坐姿/朝向、肢体
3. **穿着服饰**：风格、款式、颜色、材质
4. **整体风格**：画质、光影、氛围感、镜头感

**输出格式**：纯关键词，逗号分隔，不要句子，不要描述人脸。"""

    try:
        result = _call_multimodal_api(image_base64, analysis_prompt, api_key)
        logger.info("✅ 图片分析成功")
        return result
    except Exception as e:
        raise ImageAnalysisError(f"图片分析失败：{e}")


def build_reference_prompt(description: str) -> str:
    """
    基于参考图分析结果，构建用于图生图的 prompt
    
    Args:
        description: 参考图分析结果（场景/穿搭/姿态关键词）
    
    Returns:
        完整的 prompt，包含保持人物一致性的描述
    """
    # 新流程优化版提示词 - 更简洁明确
    # 开头：明确指令 - 保留 B 脸，套用 A 的场景/穿搭/姿态
    # 强化人物一致性指令，放在最前面确保模型优先遵循
    instruction = """【极高优先级 - 必须 100% 遵守】这是一张人物一致性图生图任务。输入图片是小柔的头像，必须严格保持小柔的脸部特征完全不变！

【脸部锁定 - 禁止改变】
- 严格保留输入图片的人脸五官、脸型、神态、眼睛、鼻子、嘴巴、眉毛、耳朵完全不变
- 不要改变脸型、下巴轮廓、颧骨形状、下颌线
- 不要改变眼睛形状、大小、间距、眼神
- 不要改变鼻子形状、鼻梁高度、鼻翼宽度
- 不要改变嘴唇厚度、嘴角形状、唇色
- 不要改变发型、发色、发量、刘海
- 人物身份必须是小柔，绝对不能变成其他人

【允许改变的内容】
- 只替换参考图的全身穿搭、姿态、背景与风格
- 可以调整光线、色调、氛围
- 可以改变拍摄角度、景深、构图

【反向提示词 - 防止脸部变化】
(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), 
bad anatomy, cloned face, different face, different person, wrong identity, 
poorly drawn face, mutation, bad proportions, (blur, out of focus:1.2),
facial distortion, inconsistent face, changed features, altered identity"""
    
    # 基础风格标签 - 减少妆容感，清淡妆容，性感妩媚
    base_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，无腮红，性感妩媚，女人味十足，迷人眼神，撩人姿态"
    
    # 真实感标签 - 强调自然融合
    realistic_tags = "超高写实，面部清晰自然，光影统一，细节真实，比例正常，无违和融合，高质量人像"
    
    # 质量标签 - 强调自然摄影、真实无 AI 感
    quality_tags = "自然摄影，真实照片，无 AI 感，无塑料感，真实光影，自然质感，细节丰富，色彩自然，人物高清，脸部高清，五官清晰，皮肤细腻，发丝清晰"
    
    # 动作自然标签 - 强调姿势自然、表情生动、生活化
    natural_pose_tags = "动作自然，姿势舒展，表情生动，神态自然，肢体放松，不僵硬，不做作，生活化姿态，日常动作，自然互动，抓拍感，动态感，流畅动作，舒展肢体，放松状态，姿势自然，体态优美，动作流畅，姿态优雅，肢体协调，动作舒展"
    
    # 腿部质量标签 - 专门针对腿部优化
    leg_quality_tags = "完美腿部比例，标准人体结构，腿部细节清晰，膝盖结构正确，脚踝结构正确，腿部光影自然，腿部皮肤质感真实，腿部线条优美，正常腿长比例，双腿完整，腿部无畸形"
    
    # 反向提示词 - 强化避免畸形问题（特别加强腿部约束）
    negative_tags = "避免畸形，避免多手多腿，避免多余肢体，避免肢体扭曲，避免肢体融合，避免肢体重复，正常人体结构，双手双脚，比例正确，避免动作僵硬，避免姿势刻板，避免表情呆板，避免摆拍感，避免奇怪姿势，避免不自然动作，避免扭曲肢体，避免怪异体态，避免不协调动作，避免腿部畸形，避免腿部融合，避免腿部扭曲，避免多余膝盖，避免腿部消失，避免腿部过长，避免腿部过短，避免腿部比例失调，避免腿部细节模糊，避免腿部结构错误，避免膝盖畸形，避免脚踝畸形，(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), bad anatomy, extra limbs, mutated hands, poorly drawn hands, poorly drawn face, mutation, cloned face, bad proportions, floating limbs, disconnected limbs, malformed hands, malformed legs, extra legs, missing legs, fused legs, mutated legs, (malformed legs:1.4), (extra legs:1.4), (fused legs:1.3), (bad legs:1.3), (missing legs:1.3), (mutated legs:1.3), blur, out of focus, long neck, long body, bad hands, missing fingers, extra digit, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry"
    
    # 组合完整 prompt - 加入动作自然化和腿部优化
    full_prompt = f"{instruction}。{description}。{base_style}。{realistic_tags}。{quality_tags}。{natural_pose_tags}。{leg_quality_tags}。{negative_tags}"
    
    return full_prompt



def analyze_image_file(image_path: str) -> Optional[str]:
    """
    分析图片文件，返回优化后的 prompt（P1 修复 - 添加路径验证）
    
    Args:
        image_path: 图片路径
    
    Returns:
        优化后的 prompt，失败返回 None
    """
    try:
        # P1 修复：验证路径安全性
        
        # 检查文件是否存在
        if not os.path.exists(image_path):
            logger.error(f"文件不存在：{image_path}")
            return None
        
        # 检查文件是否在允许的目录
        if not _is_path_allowed(image_path):
            logger.error(f"⚠️ 文件路径不在允许范围内：{image_path}")
            return None
        
        # 加载 API Key
        api_key = config.get_api_key()
        
        # 分析参考图
        description = analyze_image(image_path, api_key)
        # H-3 修复：不记录分析结果内容，只记录成功状态（防止泄露敏感图片内容）
        logger.info("✅ 图片分析成功")
        
        # 构建用于图生图的 prompt
        prompt = build_reference_prompt(description)
        
        return prompt
        
    except (ConfigurationError, ImageAnalysisError) as e:
        logger.error(f"❌ 错误：{e}")
        return None
    except Exception as e:
        logger.error(f"❌ 错误：{e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 image_analyzer.py <图片路径>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        logger.error(f"图片不存在：{image_path}")
        sys.exit(1)
    
    # P19-P2-NEW-3 修复：复用 _is_path_allowed 函数
    if not _is_path_allowed(image_path):
        logger.error(f"图片路径不在允许范围内：{image_path}")
        sys.exit(1)
    
    result = analyze_image_file(image_path)
    
    if result:
        print(result)
        sys.exit(0)
    else:
        sys.exit(1)
