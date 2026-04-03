#!/usr/bin/env python3
"""config.py - 小柔 AI 统一配置模块

提供统一的配置管理，包括：
- API Key 加载
- 临时目录配置
- 轮询间隔配置
- 日志级别配置
"""

import os
import re
import json
import tempfile
from pathlib import Path
from typing import Optional


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


class Config:
    """单例配置类"""
    _instance: Optional['Config'] = None
    _api_key: Optional[str] = None
    _temp_dir: Optional[Path] = None
    
    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_api_key(self) -> str:
        """
        获取 DashScope API Key
        
        优先级：
        1. 环境变量 DASHSCOPE_API_KEY
        2. ~/.openclaw/openclaw.json 配置
        
        Returns:
            API Key 字符串
            
        Raises:
            ConfigurationError: API Key 未配置
        """
        if self._api_key:
            return self._api_key
        
        # 1. 环境变量优先
        api_key = os.environ.get('DASHSCOPE_API_KEY', '')
        if api_key and self._is_valid_api_key(api_key):
            self._api_key = api_key
            return api_key
        
        # 2. 从配置文件加载
        config_file = Path.home() / '.openclaw/openclaw.json'
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
                
                # 多种配置位置兼容
                api_key = (
                    config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '') or
                    config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
                )
                
                if api_key and self._is_valid_api_key(api_key):
                    self._api_key = api_key
                    return api_key
            except Exception:
                pass
        
        raise ConfigurationError("API Key 未配置，请设置环境变量 DASHSCOPE_API_KEY 或配置 ~/.openclaw/openclaw.json")
    
    def _is_valid_api_key(self, key: str) -> bool:
        """验证 API Key 格式"""
        return bool(re.match(r'^sk-[a-zA-Z0-9]{20,}$', key))
    
    def get_temp_dir(self) -> Path:
        """
        获取临时目录
        
        优先级：
        1. 环境变量 XIAOROU_TEMP_DIR
        2. 系统临时目录 /tmp/xiaorou
        
        Returns:
            临时目录 Path 对象
        """
        if self._temp_dir:
            return self._temp_dir
        
        # 使用环境变量或默认路径
        temp_dir_str = os.environ.get('XIAOROU_TEMP_DIR', '/tmp/xiaorou')
        temp_dir = Path(temp_dir_str)
        
        # 创建目录（设置安全权限）
        temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        self._temp_dir = temp_dir
        return temp_dir
    
    def get_selfie_dir(self) -> Path:
        """获取自拍保存目录"""
        return self.get_temp_dir() / 'selfies'
    
    def get_video_dir(self) -> Path:
        """获取视频保存目录"""
        return self.get_temp_dir() / 'videos'
    
    def get_poll_interval(self) -> int:
        """
        获取轮询间隔（秒）
        
        默认：10 秒
        环境变量：XIAOROU_POLL_INTERVAL
        """
        return int(os.environ.get('XIAOROU_POLL_INTERVAL', '10'))
    
    def get_max_wait(self) -> int:
        """
        获取最大等待时间（秒）
        
        默认：600 秒（10 分钟）
        环境变量：XIAOROU_MAX_WAIT
        """
        return int(os.environ.get('XIAOROU_MAX_WAIT', '600'))
    
    def get_log_level(self) -> str:
        """
        获取日志级别
        
        默认：INFO
        环境变量：XIAOROU_LOG_LEVEL
        """
        return os.environ.get('XIAOROU_LOG_LEVEL', 'INFO').upper()
    
    def get_feishu_target(self) -> str:
        """
        获取飞书目标用户
        
        默认：user:ou_0668d1ec503978ef15adadd736f34c46
        环境变量：AEVIA_TARGET
        """
        return os.environ.get('AEVIA_TARGET', 'user:ou_0668d1ec503978ef15adadd736f34c46')


# 全局配置实例
config = Config()


# 工具函数
def is_valid_api_key(key: str) -> bool:
    """验证 API Key 格式"""
    return bool(re.match(r'^sk-[a-zA-Z0-9]{20,}$', key))


def get_temp_file(prefix: str, suffix: str = '') -> Path:
    """
    获取临时文件路径
    
    Args:
        prefix: 文件名前缀
        suffix: 文件扩展名
    
    Returns:
        临时文件路径
    """
    import time
    timestamp = int(time.time())
    temp_dir = config.get_temp_dir()
    return temp_dir / f"{prefix}_{timestamp}{suffix}"
