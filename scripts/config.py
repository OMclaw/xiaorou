#!/usr/bin/env python3
"""config.py - 小柔 AI 精简配置模块"""

import os
import re
import json
from pathlib import Path
from typing import Optional


class ConfigurationError(Exception):
    """配置错误"""
    pass


class Config:
    """单例配置类"""
    _instance: Optional['Config'] = None
    _api_key: Optional[str] = None
    
    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_api_key(self) -> str:
        """获取 API Key（环境变量 > 配置文件）"""
        if self._api_key:
            return self._api_key
        
        # 环境变量优先
        api_key = os.environ.get('DASHSCOPE_API_KEY', '')
        if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
            self._api_key = api_key
            return api_key
        
        # 配置文件
        config_file = Path.home() / '.openclaw/openclaw.json'
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
                api_key = (
                    config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '') or
                    config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
                )
                if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
                    self._api_key = api_key
                    return api_key
            except Exception as e:
                logger.debug(f"读取配置文件失败：{e}")  # P2 修复：使用 debug 避免泄露路径
        
        raise ConfigurationError("API Key 未配置")
    
    def get_temp_dir(self) -> Path:
        """获取临时目录"""
        temp_dir = Path(os.environ.get('XIAOROU_TEMP_DIR', '/tmp/xiaorou'))
        temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        return temp_dir
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return os.environ.get('XIAOROU_LOG_LEVEL', 'INFO').upper()
    
    def get_feishu_target(self) -> str:
        """获取飞书目标用户"""
        return os.environ.get('AEVIA_TARGET', '')


# 全局实例
config = Config()
