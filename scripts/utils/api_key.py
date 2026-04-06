#!/usr/bin/env python3
"""API Key 管理工具（统一加载逻辑）"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """配置错误"""
    pass

# API Key 验证正则（统一格式）
API_KEY_PATTERN = r'^sk-[a-zA-Z0-9]{20,}$'


def load_api_key_from_env() -> Optional[str]:
    """从环境变量加载 API Key"""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if api_key and re.match(API_KEY_PATTERN, api_key):
        logger.info("✓ 从环境变量加载 API Key")
        return api_key
    return None


def load_api_key_from_config(config_path: Optional[str] = None) -> Optional[str]:
    """从配置文件加载 API Key"""
    if config_path is None:
        config_path = str(Path.home() / '.openclaw/openclaw.json')
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        logger.debug(f"配置文件不存在：{config_path}")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 尝试多个路径
        api_key = (
            config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '') or
            config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
        )
        
        if api_key and re.match(API_KEY_PATTERN, api_key):
            logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
            return api_key
        
        logger.debug("配置文件中未找到有效的 API Key")
        return None
        
    except Exception as e:
        logger.debug(f"读取配置文件失败：{e}")
        return None


def get_api_key() -> str:
    """
    获取 API Key（环境变量 > 配置文件）
    
    Returns:
        API Key
        
    Raises:
        ConfigurationError: 如果未找到有效的 API Key
    """
    # 环境变量优先
    api_key = load_api_key_from_env()
    if api_key:
        return api_key
    
    # 配置文件
    api_key = load_api_key_from_config()
    if api_key:
        return api_key
    
    raise ConfigurationError(
        "API Key 未配置\n"
        "请配置环境变量 DASHSCOPE_API_KEY 或 ~/.openclaw/openclaw.json"
    )


def validate_api_key(api_key: str) -> bool:
    """验证 API Key 格式"""
    return bool(re.match(API_KEY_PATTERN, api_key))
