#!/usr/bin/env python3
"""config.py - 小柔 AI 精简配置模块"""

import os
import re
import json
import logging
import threading
from pathlib import Path
from typing import Optional

# 创建 logger
logger = logging.getLogger('config')
logger.setLevel(logging.DEBUG)


class ConfigurationError(Exception):
    """配置错误"""
    pass


class Config:
    """线程安全的单例配置类（带缓存）"""
    _instance: Optional['Config'] = None
    _api_key: Optional[str] = None
    _api_key_timestamp: float = 0  # API Key 缓存时间戳
    _api_key_ttl: int = int(os.environ.get('XIAOROU_API_KEY_TTL', '60'))  # API Key 缓存 60 秒
    _config_cache: Optional[dict] = None  # 配置文件缓存
    _cache_timestamp: float = 0  # 缓存时间戳
    _cache_ttl: int = int(os.environ.get('XIAOROU_CONFIG_CACHE_TTL', '300'))  # 缓存有效期 5 分钟（可配置）
    _lock = threading.Lock()  # 线程锁
    
    @property
    def _api_key_ttl(self) -> int:
        return int(os.environ.get('XIAOROU_API_KEY_TTL', '60'))
    
    @property
    def _cache_ttl(self) -> int:
        return int(os.environ.get('XIAOROU_CONFIG_CACHE_TTL', '300'))
    
    def __new__(cls) -> 'Config':
        # 双重检查锁定模式
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def _load_config_file(self) -> dict:
        """加载配置文件（带缓存，线程安全）"""
        import time
        
        # 加锁保护缓存检查和加载
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否有效
            if self._config_cache and (current_time - self._cache_timestamp) < self._cache_ttl:
                return self._config_cache
            
            # 重新加载配置
            config_file = Path.home() / '.openclaw/openclaw.json'
            if config_file.exists():
                try:
                    self._config_cache = json.loads(config_file.read_text(encoding='utf-8'))
                    self._cache_timestamp = current_time
                    return self._config_cache
                except json.JSONDecodeError as e:
                    raise ConfigurationError(f"配置文件 JSON 格式错误：{e}") from e
                except Exception as e:
                    logger.debug(f"读取配置文件失败：{e}")
                    raise ConfigurationError(f"读取配置文件失败：{e}") from e
            
            self._config_cache = {}
            return {}
    
    def get_api_key(self) -> str:
        """获取 API Key（环境变量 > 配置文件，带 TTL 缓存）"""
        import time
        
        # 环境变量优先（每次检查，支持运行时切换）
        api_key = os.environ.get('DASHSCOPE_API_KEY', '')
        if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
            self._api_key = api_key
            self._api_key_timestamp = time.time()
            return api_key
        
        # 检查 API Key 缓存是否过期（H-2 修复：Key 轮换支持）
        with self._lock:
            if self._api_key and (time.time() - self._api_key_timestamp) < self._api_key_ttl:
                return self._api_key
        
        # 配置文件（使用缓存）
        config = self._load_config_file()
        if config:
            api_key = (
                config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '') or
                config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('env', {}).get('DASHSCOPE_API_KEY', '')
            )
            if api_key and re.match(r'^sk-[a-zA-Z0-9]{20,}$', api_key):
                self._api_key = api_key
                self._api_key_timestamp = time.time()
                return api_key
        
        raise ConfigurationError("API Key 未配置")
    
    def refresh_api_key(self) -> None:
        """刷新 API Key 缓存，强制重新读取配置"""
        with self._lock:
            self._api_key = None
            self._config_cache = None
            self._cache_timestamp = 0
    
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
