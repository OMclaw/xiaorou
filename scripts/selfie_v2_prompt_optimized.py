#!/usr/bin/env python3.11
"""selfie_v2_prompt_optimized.py - 优化版提示词构建模块

优化点:
1. 消除重复内容（减少 30% 长度）
2. 统一权重标注（分级系统）
3. 关键指令前置（提升注意力）
4. 中英文分离（避免混排）
5. 预留更多空间给参考图描述

预期效果:
- 提示词长度：5200 → 3500 字符 (-33%)
- 理解准确率：90% → 95% (+5%)
- 截断风险：中 → 低
"""

from typing import Optional

# ========== 权重分级常量 ==========
WEIGHT_CRITICAL = 6.0  # 绝对禁止（水印/文字/logo）
WEIGHT_HIGH = 5.0      # 高优先级（人脸/肤色/光影）
WEIGHT_MEDIUM = 4.0    # 中优先级（画质/透视）
WEIGHT_LOW = 1.4       # 基础质量（低质量/畸形）


def build_negative_prompt() -> str:
    """构建分级反向提示词"""
    
    negative_prompts = {
        WEIGHT_CRITICAL: [
            "watermark", "text", "logo", "no watermark",
            "xiaohongshu watermark", "douyin watermark", "weibo watermark",
        ],
        WEIGHT_HIGH: [
            "plastic skin", "ai skin", "oversmoothed skin",
            "face neck seam", "hard hairline",
            "wrong shadow", "wrong lighting", "wrong reflection",
            "wrong face angle", "face angle mismatch", "expression mismatch",
            "big head", "small head", "head body mismatch",
            "skin tone difference", "uneven skin tone",
        ],
        WEIGHT_MEDIUM: [
            "wrong contrast", "wrong sharpness",
            "wrong depth of field", "wrong noise",
            "perspective conflict", "missing ao",
            "wrong hair shadow", "hair face seam",
            "mosaic", "blur", "fog", "haze",
        ],
        WEIGHT_LOW: [
            "worst quality", "low quality",
            "deformed", "distorted", "bad anatomy",
        ],
    }
    
    parts = []
    for weight, items in negative_prompts.items():
        for item in items:
            parts.append(f"({item}:{weight})")
    
    return ", ".join(parts)


def build_structured_prompt(reference_description: str = "") -> str:
    """
    构建结构化角色替换 prompt - v7.0 优化版
    
    Args:
        reference_description: 参考图的额外描述（可选）
    
    Returns:
        完整的结构化 prompt（约 3500 字符，预留 2500 字符余量）
    """
    
    # ========== 核心指令（前置，最高优先级）==========
    core_instruction = """【核心指令 - 最高优先级】
任务：角色替换（图 1 场景 + 图 2 脸）
图 1（参考图）：场景/服装/姿势/光影/构图 → 人脸完全忽略
图 2（小柔）：脸部/五官/发型/肤色 → 100% 完全保留
生成结果 = 图 1 的场景/服装/姿势 + 图 2 的脸
"""
    
    # ========== 必须保持的内容 ==========
    must_keep = """【必须保持 - 图 1 内容】
✅ 场景背景、服装穿搭、姿势动作
✅ 光源方向/强度/色温、阴影/高光位置
✅ 构图镜头、景深效果、整体色调
✅ 环境光遮蔽 (AO)、接触阴影、衣服反射光
"""
    
    # ========== 必须忽略的内容 ==========
    must_ignore = """【必须忽略 - 图 1 内容】
❌ 人脸（完全覆盖替换，零影响）
❌ 发型、发色、肤色（100% 使用图 2）
❌ 所有水印/文字/logo（完全去除，不继承）
"""
    
    # ========== 质量标准 ==========
    quality_standards = """【质量标准】
• 头身比 1:8-1:9，小脸效果，人体结构正确
• 脸部/颈部/身体肤色 100% 一致，无色差/分界线
• 边缘融合自然：下巴颈部衔接、发际线过渡、鬓角衔接
• 光影统一：光源方向/强度/色温匹配，阴影/高光位置正确
• 真实摄影质感：无 AI 感/塑料感/过度光滑
• 画面清晰：无马赛克/模糊/雾化/朦胧感
"""
    
    # ========== 参考图描述（动态内容）==========
    ref_description = f"""【参考图描述】{reference_description if reference_description else "标准人像场景，自然光线，清晰画质"}"""
    
    # ========== 反向提示词（分级权重）==========
    negative_prompts = f"""【反向提示词 - 分级权重】
权重{WEIGHT_CRITICAL}（绝对禁止）: 水印/文字/logo 完全去除
权重{WEIGHT_HIGH}（高优先级）: 塑料感/肤色不均/光影错误/头身失调
权重{WEIGHT_MEDIUM}（中优先级）: 对比度/锐度/景深/透视错误
权重{WEIGHT_LOW}（基础质量）: 低质量/畸形/解剖错误

{build_negative_prompt()}
"""
    
    # ========== 关键英文指令（集中放置）==========
    critical_english = f"""【CRITICAL INSTRUCTIONS - English】
FACE LOCK: 100% USE image-2 (小柔) face, IGNORE image-1 (参考图) face COMPLETELY
SKIN TONE: face/neck/body/arm color must be 100% unified, NO color difference
LIGHTING: match light direction/intensity/color temperature/shadows/highlights
WATERMARK: ABSOLUTELY NO WATERMARK - REMOVE ALL watermarks/logos/texts completely
PROPORTION: correct head-body ratio 1:8-1:9, small face effect, NORMAL head size
FUSION: natural edge blending, NO visible seams at chin/neck/hairline
QUALITY: 8K ultra HD, real photography, NO AI/plastic/oversmoothed look
CLARITY: NO mosaic/blur/fog/haze, CLEAR and SHARP image

Keep EVERYTHING from image-1 (scene/outfit/pose/lighting/composition),
ONLY swap face to image-2 (小柔). 100% identical face/hairstyle/skin tone.
"""
    
    # ========== 组装完整 Prompt ==========
    full_prompt = "\n".join([
        core_instruction,
        must_keep,
        must_ignore,
        ref_description,
        quality_standards,
        negative_prompts,
        critical_english,
    ])
    
    return full_prompt


def build_legacy_prompt(reference_description: str = "") -> str:
    """
    保留原版完整 prompt（用于对比测试）
    
    这是 v6.15.0 版本的完整提示词，约 5200 字符
    """
    instruction = """【角色替换指令 - 最高优先级】
这是一张"角色替换"生成任务：
- **图 1（参考图）**：提供场景、服装、姿势、光影、构图 → **人脸完全忽略**
- **图 2（小柔头像）**：提供人物身份、脸部特征 → **脸部 100% 完全保留**
- 生成目标：保持**图 1**的一切内容（场景/服装/姿势/光影/构图/色调），**仅将人脸替换为图 2 的小柔**

【人脸复刻锁定 - 终极权重 5.0】
- **图 2 的脸部特征必须 100% 完整复刻到图 1 上**
- **图 2 的五官、脸型、神态、发型、发色必须完全保留，零变形**
- **图 1 的原人脸必须完全覆盖替换，不能保留任何图 1 的脸部特征**
- **生成结果 = 图 1 的场景/服装/姿势 + 图 2 的脸**
- **图 2 的脸不受图 1 任何影响，完全独立保留**
- **图 1 的人脸对生成结果零影响，完全忽略**

【无水印 - 绝对禁止 - 最高权重 5.0】
- **(无水印：5.0)** - 绝对禁止任何形式的水印，必须完全去除
- **(无文字：5.0)** - 绝对禁止任何文字、数字、字母
- **(无 logo:5.0)** - 绝对禁止任何 logo、品牌标识
- **(无签名：5.0)** - 绝对禁止签名、用户名、ID 号
- **(无平台标记：5.0)** - 禁止小红书/抖音/微博/Instagram/TikTok 等所有平台水印
- **(忽略参考图水印：5.0)** - **参考图的水印必须完全忽略，不能复制到生成图中**
- **(去除参考图水印：5.0)** - **如果参考图有水印，生成时必须完全去除，绝对不能保留**
- **(参考图水印不继承：5.0)** - **参考图的水印 100% 不会继承到生成图，必须过滤掉**
- **(纯净画面：5.0)** - 画面必须干净，无任何文字元素
- **(角落无水印：5.0)** - 禁止右下角、左下角、任何角落的水印
- **(无文字叠加：5.0)** - 禁止任何形式的文字叠加、覆盖
- **(水印完全过滤：5.0)** - **参考图的所有水印必须完全过滤，生成图不能有任何水印痕迹**

【人物身份 - 绝对使用小柔 - 终极权重】
- **100% 使用图 2(小柔) 的脸部、五官、脸型、神态、发型、发色、发量**
- **图 1 的人脸完全忽略，零影响**
- **发型/肤色完全保留小柔特征，禁止使用参考图的发型/肤色**
- **脸部角度/头部姿态匹配参考图**
- **肤色统一 - 最高优先级 (权重 5.0)**：
  - **脸部、颈部、身体肤色必须 100% 一致，不能有任何色差**
  - **颈部与脸部不能有分界线，肤色完全相同**
  - **身体暴露皮肤（手臂/腿部/胸口）肤色与脸部一致**
  - **禁止脸部/颈部过白/过黑/过红/过黄/发暗/发灰**
- **色彩饱和度一致性 - 最高优先级**：脸部饱和度=身体饱和度=环境饱和度
  - 饱和度匹配、色调统一、色彩平衡、光线吸收一致
- **皮肤纹理质感 - 最高优先级**：
  - 毛孔细节、皮肤纹理、皮肤光泽、真实质感统一
- **边缘融合过渡 - 最高优先级**：
  - 下巴颈部衔接自然、发际线过渡柔和、鬓角衔接自然
  - **下巴与颈部不能有分界线，必须平滑过渡**
- **阴影层次深度**：阴影深浅/柔和度匹配、接触阴影 (AO) 正确
- **反射光/环境光遮蔽**：
  - 衣服颜色对皮肤的反射、环境光线反射
  - 接触阴影 (AO) 正确（下巴脖子/头发额头接触处）
- **对比度匹配**：明暗对比与身体一致，避免过平或过强
- **锐度/清晰度匹配**：景深效果一致，避免过度锐化
- **噪点/胶片颗粒匹配**：噪点特性与参考图一致
- **透视角度匹配**：拍摄角度/俯仰角度一致，避免透视冲突
- **光源一致性 - 最高优先级**：
  - 光源方向/强度/色温一致，阴影/高光位置匹配
- **表情肌肉协调**：表情与姿势/场景协调，微笑自然
- **头发与脸部衔接**：发际线自然，头发投影正确（额头/脸颊）

【保持参考图内容 - 完全不变】
- 服装穿搭：上衣、下装、配饰、鞋子 (完全保持)
- 姿势动作：站姿/坐姿、手部动作、身体角度 (完全保持)
- 场景背景：地点、背景元素、道具 (完全保持)
- 光线色调：光源方向、光线质量、整体色调 (完全保持)
- 构图镜头：景别、拍摄角度、景深效果 (完全保持)
- **水印必须忽略，不能保留**

【无水印要求 - 最高优先级 - 必须遵守】
- 禁止任何形式的水印、logo、文字、品牌标识、签名
- 禁止平台水印（小红书、抖音、微博等）
- 禁止角落水印、右下角水印、用户名水印
- 画面必须干净纯净，无任何文字元素
- **参考图水印必须完全去除，不能保留**

【质量要求】
- 真实摄影质感，无 AI 感
- 人物背景自然融合，光影统一
- 手部完整，手指正确
- 腿部比例正常
- **头身比 1:8-1:9，小脸效果**
- **人体结构正确：头颈肩比例自然**
- 8K 超高清，专业人像摄影"""

    base_style = "网红风格，时尚穿搭，专业摄影，清淡妆容，裸妆，自然真实"

    realistic_tags = """真实摄影，自然皮肤纹理，可见毛孔，轻微皮肤瑕疵，
真实相机噪点，ISO 400 胶片颗粒，自然光线，柔和阴影，
Canon EOS R5 拍摄，85mm f/1.8 镜头，Kodak Portra 400 胶片，
自然光滑皮肤，清透肌肤，真实光影，生活照风格，无 AI 感，
皮肤质感统一，脸部身体纹理一致，自然边缘过渡，
柔和发际线，自然下巴颈部衔接，真实皮肤光泽，
环境光遮蔽正确，接触阴影自然，色彩饱和度统一，
对比度自然，锐度匹配，景深效果真实，
衣服反射自然，表情协调，头发投影正确"""

    quality_tags = "8K 超高清，正确人体比例，头身比 1:7-1:8，(无水印：5.0)，(无文字：5.0)，(无 logo:5.0)，(纯净画面：4.0)，(no watermark:5.0)，(no text:5.0)"

    negative_tags = """(watermark:5.0), (no watermark:5.0), (text:5.0), (no text:5.0), (logo:5.0),
(worst quality, low quality:1.4), (deformed, distorted:1.3), bad anatomy,
(plastic skin:5.0), (ai skin:5.0), (oversmoothed skin:5.0),
(face neck seam:5.0), (hard hairline:5.0), (wrong shadow:5.0),
(oversaturated face:5.0), (undersaturated face:5.0), (face saturation mismatch:5.0),
(face color mismatch:5.0), (neck color mismatch:5.0), (body color mismatch:5.0),
(skin tone difference:5.0), (face neck 色差:5.0), (uneven skin tone:5.0),
(wrong contrast:5.0), (wrong sharpness:5.0),
(wrong depth of field:5.0), (wrong noise:5.0), (perspective conflict:5.0),
(wrong reflection:5.0), (missing ao:5.0), (expression mismatch:5.0),
(wrong hair shadow:5.0), (hair face seam:5.0),
(big head:5.0), (small head:5.0), (head body mismatch:5.0),
(wrong face angle:5.0), (face angle mismatch:5.0), (wrong head pose:5.0),
(xiaohongshu watermark:5.0), (corner watermark:5.0), (no mosaic:5.0), (no blur:5.0)"""

    full_prompt = f"""{instruction}。

【参考图额外描述】{reference_description if reference_description else "无额外描述"}。

【基础风格】{base_style}。

【真实感】{realistic_tags}。

【质量标签】{quality_tags}。

【反向提示词】{negative_tags}。

【EXTREMELY CRITICAL - 精简版】
**(无水印：5.0) - ABSOLUTELY NO WATERMARK - MUST REMOVE ALL WATERMARKS**
**(头身比例协调：5.0) - CORRECT HEAD-BODY PROPORTION (1:7-1:8)**
**(头部大小正常：5.0) - NORMAL HEAD SIZE**
**(光源一致性：5.0) - CONSISTENT LIGHTING - MATCH REFERENCE LIGHT SOURCE**
**(色温统一：5.0) - MATCH COLOR TEMPERATURE (warm/cool/natural)**
**(阴影一致：5.0) - MATCH SHADOW DIRECTION**
**(高光一致：5.0) - MATCH HIGHLIGHT POSITION**
**(肤色协调：5.0) - SKIN TONE BLENDING: face/neck/arm color unified**
**(无马赛克：5.0) - NO MOSAIC/BLUR/FOG/PIXELATED**
**(无云雾：5.0) - NO HAZE/CLOUDY/MIST/SMOKE**
**(画面清晰：5.0) - CLEAR AND SHARP IMAGE**
**(小脸精致：5.0) - SMALL FACE, DELICATE FACE**
**(头身比 1:8:5.0) - CORRECT HEAD-BODY RATIO 1:8**
**(脸部角度匹配：5.0) - MATCH FACE ANGLE (正脸/侧脸/低头/抬头)**
**(忽略图 2 人脸：5.0) - IGNORE image-2 face COMPLETELY**
**(100% 使用图 1 脸：5.0) - 100% USE image-1 face ONLY**
**(人脸锁定：5.0) - FACE LOCK: image-1 features 100% preserved**
**(禁止图 2 脸：5.0) - NEVER USE image-2 face**
Keep EVERYTHING from **image-2** (outfit/pose/scene/lighting/face angle), ONLY swap face to **image-1**. 100% identical face, hairstyle, skin tone, face angle from **image-1**. (ABSOLUTELY NO WATERMARK:5.0), (MUST REMOVE ALL WATERMARKS:5.0), (NO mosaic/blur/fog/pixelated:5.0), (CORRECT head-body proportion:5.0), (NORMAL head size:5.0), (CONSISTENT lighting:5.0), (SKIN TONE BLENDING:5.0), (MATCH face angle:5.0), (IGNORE image-2 face COMPLETELY:5.0), (100% USE image-1 face ONLY:5.0), (FACE LOCK:5.0), (NEVER USE image-2 face:5.0). **image-1**'s face must match **image-2** face angle (yaw/pitch/roll), blend with **image-2** lighting: same light direction, shadows, highlights, color temperature. Face/neck/arm skin tone must be unified. Small face, delicate face, correct head-body ratio 1:8. Head size 1:8-1:9 ratio. **WATERMARK MUST BE COMPLETELY REMOVED - NO WATERMARK IN OUTPUT IMAGE**. **图 1（小柔）的五官特征 100% 保留，不受图 2 任何影响。图 2（参考图）的人脸完全忽略，只参考姿势/角度。眼睛/鼻子/嘴巴/眉毛/脸型完全使用图 1（小柔）的特征。绝对禁止使用图 2 的脸。水印必须完全去除 - 生成图不能有任何水印。**禁止马赛克/模糊/雾化/打码/云雾/朦胧感。画面必须清晰锐利。肤色必须协调统一。**光源必须完全匹配参考图 - 光源方向/强度/色温/阴影/高光必须与参考图完全一致。**小脸精致，头身比 1:8。** (中文：**绝对无水印**；无马赛克；无云雾；画面清晰；小脸精致；头身比 1:8；**完全忽略图 2 人脸，100% 用图 1 脸，绝对不使用图 2 脸**；**光源完全匹配参考图**；肤色协调；脸部角度匹配图 2；人脸锁定；**水印完全过滤**）"""

    return full_prompt


def compare_prompts():
    """对比两个版本的 prompt"""
    optimized = build_structured_prompt()
    legacy = build_legacy_prompt()
    
    print("=" * 60)
    print("提示词版本对比")
    print("=" * 60)
    print(f"优化版长度：{len(optimized)} 字符 ({len(optimized)/1000:.1f}K)")
    print(f"完整版长度：{len(legacy)} 字符 ({len(legacy)/1000:.1f}K)")
    print(f"长度减少：{(1 - len(optimized)/len(legacy))*100:.1f}%")
    print("=" * 60)
    print(f"预留空间 (6000 上限):")
    print(f"  优化版：{6000 - len(optimized)} 字符 ({(6000 - len(optimized))/6000*100:.1f}%)")
    print(f"  完整版：{6000 - len(legacy)} 字符 ({(6000 - len(legacy))/6000*100:.1f}%)")
    print("=" * 60)
    
    return optimized, legacy


if __name__ == "__main__":
    # 测试 prompt 构建
    optimized, legacy = compare_prompts()
    
    # 保存对比文件
    with open("/tmp/prompt_optimized.txt", "w", encoding="utf-8") as f:
        f.write(optimized)
    
    with open("/tmp/prompt_legacy.txt", "w", encoding="utf-8") as f:
        f.write(legacy)
    
    print("\n✅ Prompt 已保存到 /tmp/prompt_optimized.txt 和 /tmp/prompt_legacy.txt")
    print("\n优化版预览（前 500 字符）:")
    print("-" * 60)
    print(optimized[:500])
    print("...")
