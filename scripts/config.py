#!/usr/bin/env python3
"""config.py - 小柔 AI 精简配置模块"""

import os
import re
import json
import logging
import threading
from pathlib import Path
from typing import Optional, List, Tuple

# 创建 logger
logger = logging.getLogger('config')
logger.setLevel(logging.DEBUG)

# P1-3 修复：支持通过环境变量扩展允许的目录列表
def get_allowed_image_dirs() -> Tuple[Path, ...]:
    """从环境变量获取允许的目录列表"""
    env_dirs = os.environ.get('XIAOROU_ALLOWED_DIRS', '')
    if env_dirs:
        # 支持冒号分隔的多个路径
        return tuple(Path(p.strip()) for p in env_dirs.split(':') if p.strip())
    # 默认目录
    return (
        Path('/home/admin/.openclaw/media/inbound'),
        Path('/tmp/openclaw'),
        Path('/tmp/xiaorou'),
    )

# 保持向后兼容的常量（使用默认值）
ALLOWED_IMAGE_DIRS = get_allowed_image_dirs()


class ConfigurationError(Exception):
    """配置错误"""
    pass


class Config:
    """线程安全的单例配置类（带缓存）"""
    _instance: Optional['Config'] = None
    _api_key: Optional[str] = None
    _api_key_timestamp: float = 0  # API Key 缓存时间戳
    _config_cache: Optional[dict] = None  # 配置文件缓存
    _cache_timestamp: float = 0  # 缓存时间戳
    _lock = threading.RLock()  # 可重入锁，防止嵌套调用死锁（P1-1 修复）
    # P3-4 修复：TTL 缓存值
    _api_key_ttl_value: Optional[int] = None
    _cache_ttl_value: Optional[int] = None
    
    @property
    def _api_key_ttl(self) -> int:
        if self._api_key_ttl_value is None:
            self._api_key_ttl_value = int(os.environ.get('XIAOROU_API_KEY_TTL', '60'))
        return self._api_key_ttl_value

    @property
    def _cache_ttl(self) -> int:
        if self._cache_ttl_value is None:
            self._cache_ttl_value = int(os.environ.get('XIAOROU_CONFIG_CACHE_TTL', '300'))
        return self._cache_ttl_value
    
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
            
            # 重新加载配置（P1-4 修复：支持环境变量指定配置文件路径）
            config_file = self._get_config_path()
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
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径（支持环境变量）"""
        # 支持环境变量指定配置文件路径
        env_path = os.environ.get('OPENCLAW_CONFIG_PATH', '')
        if env_path:
            return Path(env_path)
        # 默认路径
        return Path.home() / '.openclaw/openclaw.json'
    
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
        """获取临时目录（P0-3 修复：root UID 安全增强）"""
        if not hasattr(self, '_temp_dir_cached'):
            uid = os.getuid()
            # P0-3 修复：如果 UID 为 0(root)，使用随机后缀避免共享目录
            if uid == 0:
                import secrets
                suffix = secrets.token_hex(8)
                logger.debug("检测到 root 用户，使用随机临时目录后缀")
            else:
                suffix = str(uid)
            
            temp_dir = Path(os.environ.get('XIAOROU_TEMP_DIR', f'/tmp/xiaorou_{suffix}'))
            
            # 检查目录是否已存在且所有者不匹配
            if temp_dir.exists():
                try:
                    stat_info = temp_dir.stat()
                    if stat_info.st_uid != uid:
                        raise ConfigurationError(
                            f"临时目录所有者不匹配：{temp_dir} (所有者 UID: {stat_info.st_uid}, 当前 UID: {uid})"
                        )
                except OSError as e:
                    logger.debug(f"检查临时目录权限失败：{e}")
            
            # 创建目录（mode=0o700 确保只有当前用户可访问）
            temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._temp_dir_cached = temp_dir
            
        return self._temp_dir_cached
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return os.environ.get('XIAOROU_LOG_LEVEL', 'INFO').upper()
    
    def get_feishu_target(self) -> str:
        """获取飞书目标用户（环境变量 > 配置文件）"""
        env_target = os.environ.get('AEVIA_TARGET', '')
        if env_target:
            return env_target
        # 从配置文件读取
        config = self._load_config_file()
        return config.get('skills', {}).get('entries', {}).get('xiaorou', {}).get('config', {}).get('feishu_target', '')


# 全局实例
config = Config()
