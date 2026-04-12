#!/usr/bin/env python3
"""image_analyzer.py - 参考图分析模块 (使用 qwen3.5-plus 视觉能力)

分析参考图，提取场景、姿势、服装、光线等描述，用于后续图生图。

优化内容：
- 商拍模板结构：按服装/场景/光线/姿势/镜头顺序提取
- 真实感增强：iPhone 15 Pro Max 质感、自然皮肤褶皱、细微阴影层次
- 人物一致性：强化脸部锁定，禁止混合参考图脸部
- 手部约束：30+ 种手部问题禁止，权重最高 2.5
- 摄影参数：Canon EOS R5, 85mm f/1.2, Kodak Portra 400 胶片模拟
"""

from dashscope import MultiModalConversation
import os
import sys
import base64
import logging
import re
from pathlib import Path
from typing import Optional

# 导入统一配置
from config import config, ConfigurationError, ALLOWED_IMAGE_DIRS


# ========== 常量定义 ==========
API_TIMEOUT = int(os.environ.get('XIAOROU_API_TIMEOUT', '120'))
MAX_FILE_SIZE_MB = 20
MAX_PROMPT_LENGTH = 6000

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class ImageAnalysisError(Exception):
    """图片分析异常"""
    pass
# Prompt 标签常量（P3-3 修复：集中管理）
PROMPT_CRITICAL_FACE_WARNING = "**EXTREMELY CRITICAL: Use ONLY the face from input image (小柔), NEVER use face from reference photo!**\n**STRICTLY same person as input image, 100% identical face, ABSOLUTELY NO face swap!**"
PROMPT_FACE_WARNING2 = "**IDENTICAL face to input image, same person, no transformation, no morphing!**"
PROMPT_BASE_TEMPLATE = "An East Asian female model (小柔 - MUST use input image face, DO NOT blend or mix with reference face), mid-20s, professional commercial photography shot. {extract_clothing_from_description(description)}. Shot in {extract_location_from_description(description)}. {extract_lighting_from_description(description)} lighting. {extract_pose_from_description(description)}. Captured with iPhone 15 Pro Max, natural skin folds and wrinkles, subtle shadow layers, realistic environmental details. Magazine editorial quality, ultra-detailed skin texture, natural color grading, Kodak Portra 400 film emulation. {PROMPT_FACE_WARNING2}"
PROMPT_REFERENCE_LABEL = "【参考图细节 - 中文补充】"
PROMPT_BASE_STYLE_LABEL = "【基础风格】"
PROMPT_REALISTIC_LABEL = "【真实感】"
PROMPT_QUALITY_LABEL = "【画质】"


# P2-3 修复：路径安全检查函数（P2-5 修复：使用统一目录列表）
# P1-1 修复：Python 3.8 兼容性（is_relative_to 需要 3.9+）
def _is_path_allowed(file_path: str) -> bool:
    """检查文件路径是否在允许的目录列表内"""
    try:
        resolved = Path(file_path).resolve()
        for allowed in ALLOWED_IMAGE_DIRS:
            allowed_resolved = allowed.resolve()
            try:
                 # Python 3.9+ 使用 is_relative_to
                if resolved.is_relative_to(allowed_resolved):
                    return True
            except AttributeError:
                 # Python 3.8 备用方案：使用字符串前缀检查
                if str(resolved).startswith(str(allowed_resolved) + os.sep):
                    return True
        return False
    except Exception:
        return False


def get_image_base64(image_path: str) -> str:
    """读取图片并转换为 base64"""
     # 检查文件大小（限制 20MB）（P3-2 修复：添加空文件检查）
    file_size = os.path.getsize(image_path)
    if file_size == 0:
        raise ImageAnalysisError(f"图片文件为空：{image_path}")
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ImageAnalysisError(f"图片文件过大：{file_size / 1024 / 1024:.2f}MB（限制 {MAX_FILE_SIZE_MB}MB）")
    
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
        timeout=API_TIMEOUT   # P1-2 修复：传入超时参数
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
    
     # 构建分析 prompt - 参考商拍模板结构提取（完全忽略人脸）
    analysis_prompt = """请对这张参考图进行特征提取，**完全忽略人脸、五官、面部特征、发型**，按照商拍模板结构提取以下内容：

**【商拍模板结构 - 必须按此顺序输出】**

1. **【服装/造型】**（最高优先级，需详细描述）：
   - 上衣/连衣裙：款式、颜色、图案、材质、细节（如"黄色比基尼挂脖设计，胸前褶皱装饰，侧边系带"）
   - 下装：类型、颜色、款式细节
   - 配饰：项链/耳环/墨镜/帽子/包包/发饰等
   - 鞋子：类型、颜色、款式

2. **【场景/背景】**：
   - 地点：海滩/咖啡厅/室内/街道等
   - 背景元素：建筑、植物、道具等
   - 整体色调：冷/暖/中性

3. **【光线】**：
   - 光源方向：顺光/侧光/逆光/顶光
   - 光线质量：硬光/软光/自然光/影棚光
   - 光线效果：高光、阴影、轮廓光等

4. **【姿势/动作】**：
   - 身体姿势：站姿/坐姿/躺姿
   - 手部动作：具体手势、手拿道具等
   - 表情：微笑/眼神/情绪（不描述五官细节）

5. **【镜头/构图】**：
   - 景别：特写/半身/全身
   - 拍摄角度：平视/俯视/仰视
   - 景深：背景虚化程度

**输出格式**：按上述 5 点顺序输出，每点用完整句子详细描述，不要关键词列表。完全不要描述人脸五官。"""

    try:
        result = _call_multimodal_api(image_base64, analysis_prompt, api_key)
        logger.info("✅ 图片分析成功")
        return result
    except Exception as e:
        raise ImageAnalysisError(f"图片分析失败：{e}")


    return "Bright natural daylight"

def extract_pose_from_description(desc: str) -> str:
    """从参考图描述中提取姿势描述"""
    return "Standing pose with natural arm position"

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
    instruction = """【任务说明】
**参考图 2 生成图 1 人脸在这个场景下的图片**
**生成目标 = 小柔的脸（图 1）+ 参考图的场景/服装/光影/姿势/表情（图 2）**

【人物一致性 - 绝对禁止改变】
- **必须 100% 使用输入图片（小柔头像）的脸部**，完全保留小柔的五官、脸型、神态、发型
- **禁止使用参考图的脸部**，参考图仅提供场景/服装/姿势/光影
- **禁止混合两张图片的脸部特征**，必须完全使用输入图片的脸
- 严格保留输入图片的人脸五官、脸型、神态、眼睛、鼻子、嘴巴、眉毛、耳朵完全不变
- 不要改变脸型、下巴轮廓、颧骨形状、下颌线、额头形状
- 不要改变眼睛形状、大小、间距、眼神、眼睑、睫毛
- 不要改变鼻子形状、鼻梁高度、鼻翼宽度、鼻尖形状
- 不要改变嘴唇厚度、嘴角形状、唇色、唇形
- 不要改变发型、发色、发量、刘海、发际线
- 人物身份必须是小柔，绝对不能变成参考图里的人或其他人

【允许改变的内容 - 从参考图提取并融入 prompt】
- 全身穿搭（上衣、下装、连衣裙、配饰等）
- 姿势（站姿、坐姿、手部动作等）
- 背景与场景（海滩、咖啡厅、室内等）
- 光线、色调、氛围
- 拍摄角度、景深、构图
- 表情（微笑、眼神等）

【人物一致性反向提示词 - 终极权重】
(different face:4.0), (different person:4.0), (wrong identity:4.0), (changed face:4.0), 
(inconsistent face:4.0), (not the same person:4.0), (face from reference:4.0), (face swap:4.0),
(cloned face:3.5), (facial distortion:3.5), (altered features:3.5), (changed features:3.5),
(blended face:3.5), (mixed face:3.5), (morphed face:3.5), (transformed face:3.5),
(another person face:4.0), (reference face:4.0), (use reference face:4.0),
(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), 
bad anatomy, poorly drawn face, mutation, bad proportions, (blur, out of focus:1.2)"""
    
     # 基础风格标签 - 减少妆容感，清淡妆容，性感妩媚，自然真实
    base_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，无腮红，性感妩媚，女人味十足，迷人眼神，撩人姿态，【自然真实 - 极高优先级】动作极其自然，表情生动真实，姿态放松不僵硬，抓拍感强，生活化场景，日常自然状态，完全不做作，肢体语言流畅，神态自然有神，避免摆拍感，避免刻板姿势，避免表情呆板"
    
     # 真实感标签 - 强调自然融合
    realistic_tags = "超高写实，面部清晰自然，光影统一，细节真实，比例正常，无违和融合，高质量人像"
    
     # 质量标签 - 强调自然摄影、真实无 AI 感
    quality_tags = "自然摄影，真实照片，无 AI 感，无塑料感，真实光影，自然质感，细节丰富，色彩自然，人物高清，脸部高清，五官清晰，皮肤细腻，发丝清晰，iPhone 15 Pro Max 拍摄，手机摄影质感，真实环境细节，环境纹理清晰，背景细节丰富"
    
     # 动作自然标签 - 强调姿势自然、表情生动、生活化（极高优先级）
    natural_pose_tags = "【动作自然 - 极高优先级】动作极其自然，姿势舒展流畅，表情生动有神，神态放松自然，肢体语言流畅，完全不僵硬，完全不做作，生活化姿态，日常自然动作，与环境自然互动，抓拍感强，动态感强，动作连贯流畅，肢体舒展放松，状态轻松自然，姿势优美流畅，体态自然优美，动作协调流畅，姿态优雅自然，肢体协调统一，动作舒展大方，【禁止僵硬摆拍】【禁止刻板姿势】【禁止表情呆板】【禁止不自然动作】"
    
     # 腿部质量标签 - 专门针对腿部优化
    leg_quality_tags = "完美腿部比例，标准人体结构，腿部细节清晰，膝盖结构正确，脚踝结构正确，腿部光影自然，腿部皮肤质感真实，腿部线条优美，正常腿长比例，双腿完整，腿部无畸形"
    
     # 【新增】专业摄影参数 - 光影和景深核心优化
    photography_params = """专业人像摄影，Canon EOS R5，RF 85mm f/1.2L USM 镜头，f/1.8-f/2.8 大光圈，浅景深效果，背景明显虚化，焦点锐利在人物身上，背景虚化过渡自然，奶油般虚化效果，1/500 秒快门，ISO 100-400，专业级画质，RAW 格式后期，电影级调色"""
    
     # 【新增】光影细节 - 核心优化
    lighting_detail = """自然光影层次丰富，光线方向明确，主光从侧方或侧逆光照射，形成明显的明暗对比，高光区域柔和不过曝，阴影区域有细节不死黑，环境光反射自然，次表面散射效果明显（皮肤透光感），真实光线物理特性，专业三点布光或自然光模拟，光线色温准确（暖光约 3200K 或自然光约 5600K），光线质量柔和，阴影边缘过渡平滑"""
    
     # 【新增】手部完整性 - 重点强调
    hand_integrity = """双手完整可见，五指清晰，手指数量正确（每只手 5 根手指），手指长度比例正常，手指关节结构正确，指甲细节清晰，手掌纹理自然，手部皮肤质感真实，手部姿势自然不扭曲，双手对称，手肘手腕结构正确，手部光影与身体一致，手部无畸形无融合无缺失，完整的双手十指，手部细节高清"""
    
     # 【新增】景深细节 - 核心优化
    depth_of_field = """浅景深效果，背景明显虚化但保持可识别轮廓，前景人物清晰锐利，中景过渡自然，背景虚化呈现圆形光斑（焦外成像），虚化程度与 85mm f/1.8 镜头匹配，焦点锁定人物眼睛和脸部，身体略微失焦营造立体感，地面和背景建筑虚化程度递增，空间层次分明，三维立体感强，真实光学虚化非算法模糊"""
    
     # 【新增】皮肤质感细节 - 真实肌肤表现
    skin_texture_tags = """皮肤纹理清晰可见，毛孔细节自然分布，真实肌肤质感而非塑料感，轻微皮肤纹理和细小瑕疵保留，健康肤色均匀，自然肤色过渡，皮肤光泽自然（非油光），无过度磨皮或美颜，保留真实皮肤细节如细小皱纹、皮肤纹理走向，细腻肤质但非完美无瑕，真实皮下组织感（血管隐约可见），微妙的皮肤不规则性，真实人脸纹理而非 AI 生成的平滑表面，自然皮肤褶皱，皮肤褶皱细节真实，细微阴影层次，皮肤光影过渡自然，皮肤质感立体"""
    
     # 【新增】胶片质感 - 增加真实照片特征
    film_emulation_tags = """Kodak Portra 400 胶片色彩科学模拟，Fujifilm Pro 400H 色调倾向，轻微胶片颗粒感（ISO 400 级别），胶片动态范围特性，高光柔和滚降，阴影细节丰富，轻微暗角效果（镜头特性），细微镜头色散（紫边/绿边），真实光学镜头缺陷而非完美数码感，胶片色彩饱和度和对比度特性"""
    
     # 【新增】环境融合 - 人物与背景自然融合
    environment_blend = """人物与背景自然融合无违和感，环境光遮蔽（AO）效果明显（人物与地面接触处有阴影），接触阴影真实，人物在地面投射出清晰影子，影子方向与光源一致，环境反射（人物身上有背景色反射），色彩呼应（人物服装颜色与背景色调协调），背景虚化过渡自然无硬边，景深层次分明（前景 - 中景 - 背景），空间感强，三维立体感，真实空间关系和透视，真实的环境细节，环境纹理清晰，背景物体细节丰富，环境光影层次分明"""
    
     # 【精简】反向提示词 - 去重并统一权重（<500 字符）
    negative_tags = """避免 AI 感，避免塑料感，避免过度光滑，避免数码合成感，避免 3D 渲染感，避免卡通插画感，避免不自然光影，避免畸形，避免多余肢体，正常人体结构，比例正确，避免动作僵硬，避免表情呆板，避免手部畸形，避免手指融合，避免腿部畸形，
    (no hands:2.5), (missing hands:2.5), (bad hands:2.0), (malformed hands:2.0), (extra fingers:1.8), (fused fingers:2.0), (missing limbs:2.0), (disconnected limbs:1.8), (poorly drawn hands:2.0), (poorly drawn face:1.5), (bad anatomy:1.5), (worst quality, low quality:1.4), blur, out of focus, 3d, cgi, cartoon, anime, digital art"""
    
     # 组合完整 prompt - 商拍模板框架 + 人物一致性 + 参考图细节
    full_prompt = f"""{instruction}。

【商拍模板框架 - 英文专业描述 + 终极人物一致性】
**EXTREMELY CRITICAL: Use ONLY the face from input image (小柔), NEVER use face from reference photo!**
**STRICTLY same person as input image, 100% identical face, ABSOLUTELY NO face swap!**
An East Asian female model (小柔 - MUST use input image face, DO NOT blend or mix with reference face), mid-20s, professional commercial photography shot. {extract_clothing_from_description(description)}. Shot in {extract_location_from_description(description)}. {extract_lighting_from_description(description)} lighting. {extract_pose_from_description(description)}. Captured with iPhone 15 Pro Max, natural skin folds and wrinkles, subtle shadow layers, realistic environmental details. Magazine editorial quality, ultra-detailed skin texture, natural color grading, Kodak Portra 400 film emulation. **IDENTICAL face to input image, same person, no transformation, no morphing!**

【参考图细节 - 中文补充】{description}。

【基础风格】{base_style}。

【真实感】{realistic_tags}。

【画质】{quality_tags}。

【动作自然】{natural_pose_tags}。

【腿部质量】{leg_quality_tags}。

【手部完整】{hand_integrity}。

【摄影参数】{photography_params}。

【光影细节】{lighting_detail}。

【景深效果】{depth_of_field}。

【皮肤质感】{skin_texture_tags}。

【胶片质感】{film_emulation_tags}。

【环境融合】{environment_blend}。

【反向提示词】{negative_tags}"""
    
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
