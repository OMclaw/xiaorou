#!/usr/bin/env python3
"""face_enhancer.py - 脸部一致性增强模块

使用 InsightFace 进行后处理换脸，确保生成的图片脸部 100% 与小柔头像一致。

安装依赖：
    pip install insightface onnxruntime-gpu opencv-python

使用方式：
    python3 face_enhancer.py <生成的图片路径> <小柔头像路径> [输出路径]
"""

import os
import sys
import logging
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


class FaceEnhancerError(Exception):
    """脸部增强错误"""
    pass


def check_dependencies() -> Tuple[bool, str]:
    """检查依赖是否已安装"""
    missing = []
    
    try:
        import insightface
    except ImportError:
        missing.append('insightface')
    
    try:
        import onnxruntime
    except ImportError:
        missing.append('onnxruntime')
    
    try:
        import cv2
    except ImportError:
        missing.append('opencv-python')
    
    if missing:
        return False, f"缺少依赖：{', '.join(missing)}\n请运行：pip install {' '.join(missing)}"
    
    return True, "依赖检查通过"


def init_face_analysis(providers: list = None):
    """初始化人脸分析模型"""
    from insightface.app import FaceAnalysis
    
    if providers is None:
        # 优先使用 GPU，如果没有则回退到 CPU
        try:
            import onnxruntime
            gpu_providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            # 测试 GPU 是否可用
            available_providers = onnxruntime.get_available_providers()
            if 'CUDAExecutionProvider' not in available_providers:
                logger.info("GPU 不可用，使用 CPU 运行")
                providers = ['CPUExecutionProvider']
            else:
                providers = gpu_providers
        except:
            providers = ['CPUExecutionProvider']
    
    app = FaceAnalysis(providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def extract_face_features(app, image_path: str) -> Optional[dict]:
    """
    从图片中提取人脸特征
    
    Args:
        app: FaceAnalysis 实例
        image_path: 图片路径
    
    Returns:
        包含人脸特征的字典，或 None（如果未检测到人脸）
    """
    img = cv2.imread(image_path)
    if img is None:
        logger.error(f"无法读取图片：{image_path}")
        return None
    
    faces = app.get(img)
    
    if len(faces) == 0:
        logger.warning(f"未检测到人脸：{image_path}")
        return None
    
    if len(faces) > 1:
        logger.warning(f"检测到 {len(faces)} 张人脸，使用最大的一张")
        # 选择最大的人脸（面积最大）
        faces = sorted(faces, key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
    
    face = faces[0]
    return {
        'face': face,
        'embedding': face.normed_embedding,
        'bbox': face.bbox,
        'landmarks': face.landmarks
    }


def swap_face(source_img: np.ndarray, target_face: dict, source_face: dict, 
              swapper=None) -> np.ndarray:
    """
    换脸操作
    
    Args:
        source_img: 目标图片（要换脸的图）
        target_face: 目标人脸特征（图中的人脸）
        source_face: 源人脸特征（小柔的脸）
        swapper: InsightFace Swapper 实例
    
    Returns:
        换脸后的图片
    """
    from insightface.model_zoo import get_model
    
    if swapper is None:
        # 加载换脸模型
        swapper = get_model('inswapper_128.onnx', download=True)
    
    # 执行换脸
    result = swapper.get(source_img, target_face['face'], source_face['face'], paste_back=True)
    return result


def enhance_face_consistency(generated_image: str, reference_face_image: str, 
                            output_path: Optional[str] = None) -> str:
    """
    增强脸部一致性 - 后处理换脸
    
    Args:
        generated_image: AI 生成的图片路径
        reference_face_image: 参考脸部图片（小柔头像）
        output_path: 输出路径（可选，默认在原路径基础上添加_enhanced 后缀）
    
    Returns:
        换脸后的图片路径
    """
    # 检查依赖
    ok, msg = check_dependencies()
    if not ok:
        raise FaceEnhancerError(msg)
    
    from insightface.model_zoo import get_model
    
    # 验证文件存在
    if not os.path.exists(generated_image):
        raise FaceEnhancerError(f"生成的图片不存在：{generated_image}")
    
    if not os.path.exists(reference_face_image):
        raise FaceEnhancerError(f"参考头像不存在：{reference_face_image}")
    
    # 初始化模型
    logger.info("🔧 初始化人脸分析模型...")
    app = init_face_analysis()
    
    # 提取小柔人脸特征
    logger.info(f"👤 提取参考人脸特征：{reference_face_image}")
    source_face = extract_face_features(app, reference_face_image)
    if source_face is None:
        raise FaceEnhancerError("未能在参考头像中检测到人脸")
    
    # 读取生成的图片
    logger.info(f"📷 读取生成的图片：{generated_image}")
    gen_img = cv2.imread(generated_image)
    if gen_img is None:
        raise FaceEnhancerError(f"无法读取生成的图片：{generated_image}")
    
    # 检测生成图片中的人脸
    logger.info("🔍 检测生成图片中的人脸...")
    gen_faces = app.get(gen_img)
    
    if len(gen_faces) == 0:
        logger.warning("生成图片中未检测到人脸，跳过换脸处理")
        return generated_image
    
    if len(gen_faces) > 1:
        logger.warning(f"检测到 {len(gen_faces)} 张人脸，使用最大的一张进行换脸")
        gen_faces = sorted(gen_faces, key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
    
    target_face = gen_faces[0]
    
    # 加载换脸模型
    logger.info("🎭 加载换脸模型...")
    swapper = get_model('inswapper_128.onnx', download=True)
    
    # 执行换脸
    logger.info("✨ 执行换脸...")
    result = swapper.get(gen_img, target_face, source_face['face'], paste_back=True)
    
    # 确定输出路径
    if output_path is None:
        gen_path = Path(generated_image)
        output_path = str(gen_path.parent / f"{gen_path.stem}_enhanced{gen_path.suffix}")
    
    # 保存结果
    logger.info(f"💾 保存结果到：{output_path}")
    cv2.imwrite(output_path, result)
    
    logger.info("✅ 脸部一致性增强完成")
    return output_path


def main():
    """命令行入口"""
    if len(sys.argv) < 3:
        print("用法：python3 face_enhancer.py <生成的图片路径> <小柔头像路径> [输出路径]")
        print("\n示例：")
        print("  python3 face_enhancer.py /tmp/generated.jpg /path/to/xiaorou.png")
        print("  python3 face_enhancer.py /tmp/generated.jpg /path/to/xiaorou.png /tmp/enhanced.jpg")
        sys.exit(1)
    
    generated_image = sys.argv[1]
    reference_face = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        result_path = enhance_face_consistency(generated_image, reference_face, output_path)
        logger.info(f"✅ 处理完成：{result_path}")
        print(result_path)
        sys.exit(0)
    except FaceEnhancerError as e:
        logger.error(f"❌ 错误：{e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 未知错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
