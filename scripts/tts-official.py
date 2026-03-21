#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts-official.py - 文字转语音 (使用阿里云官方 SDK 示例代码)

基于阿里云官方示例：https://help.aliyun.com/zh/model-studio/cosyvoice-python-sdk

使用示例:
  python tts-official.py "你好，我是小柔" /tmp/voice.mp3
"""

import os
import sys
import json
import logging
import time
import uuid
import websocket
import base64
import threading

# ============================================
# 日志配置
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('cosyvoice-official')

# ============================================
# 配置
# ============================================
# WebSocket URL（北京地域）
WS_URL = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型和音色
DEFAULT_MODEL = "cosyvoice-v3-flash"
DEFAULT_VOICE = "longanyang"  # 温暖女声（推荐）

# ============================================
# 加载 API Key
# ============================================
def load_api_key():
    """从环境变量或配置文件加载 API Key"""
    # 优先使用环境变量
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    
    if api_key and api_key.startswith('sk-'):
        return api_key
    
    # 尝试从 OpenClaw 配置文件加载
    config_file = os.path.expanduser('~/.openclaw/openclaw.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            api_key = config.get('models', {}).get('providers', {}).get('dashscope', {}).get('apiKey', '')
            
            if api_key and api_key.startswith('sk-'):
                logger.info("✓ 从 OpenClaw 配置文件加载 API Key")
                return api_key
        except Exception as e:
            logger.debug(f"读取配置文件失败：{e}")
    
    raise Exception("无法加载 API Key，请设置 DASHSCOPE_API_KEY 环境变量")

# ============================================
# TTS 调用类 (基于官方示例)
# ============================================
class CosyVoiceTTS:
    def __init__(self, api_key, model=DEFAULT_MODEL, voice=DEFAULT_VOICE):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.ws_url = f"{WS_URL}?api-key={api_key}"
        self.audio_data = b''
        self.done = threading.Event()
        self.error = None
        self.request_id = None
        self.first_package_time = None
        self.connection_start_time = None
        
    def on_message(self, ws, message):
        """接收消息回调"""
        try:
            data = json.loads(message)
            
            # 获取 request_id
            if 'request_id' in data:
                self.request_id = data['request_id']
            
            # 检查错误
            if 'error' in data:
                self.error = data['error'].get('message', '未知错误')
                logger.error(f"API 错误：{self.error}")
                self.done.set()
                return
            
            # 检查输出
            if 'output' in data:
                output = data['output']
                
                # 接收音频数据
                if 'audio' in output:
                    audio_base64 = output['audio']
                    self.audio_data += base64.b64decode(audio_base64)
                    
                    # 记录首包延迟
                    if self.first_package_time is None:
                        self.first_package_time = time.time()
                        delay_ms = int((self.first_package_time - self.connection_start_time) * 1000)
                        logger.info(f"✓ 首包延迟：{delay_ms}ms")
                
                # 检查完成状态
                if output.get('status') == 'COMPLETED':
                    logger.info(f"✓ 音频生成完成，总大小：{len(self.audio_data)} bytes")
                    self.done.set()
                    
        except Exception as e:
            logger.error(f"处理消息失败：{e}")
            self.error = str(e)
            self.done.set()
    
    def on_error(self, ws, error):
        """错误回调"""
        logger.error(f"WebSocket 错误：{error}")
        self.error = str(error)
        self.done.set()
    
    def on_close(self, ws, close_status_code, close_msg):
        """关闭回调"""
        logger.debug(f"WebSocket 关闭：{close_status_code} - {close_msg}")
    
    def on_open(self, ws):
        """打开回调 - 发送请求"""
        logger.debug("WebSocket 连接已建立")
        self.connection_start_time = time.time()
        
        # 构建请求（包含 header 字段）
        request_id = str(uuid.uuid4())
        self.request_id = request_id
        
        request_msg = {
            "header": {
                "task_id": request_id
            },
            "model": self.model,
            "input": {
                "text": self.text_to_synthesize
            },
            "parameters": {
                "voice": self.voice,
                "format": "mp3",
                "sample_rate": 24000,
                "volume": 50,
                "rate": 1.0,
                "pitch": 1.0
            }
        }
        
        ws.send(json.dumps(request_msg))
        logger.info(f"已发送请求：text={self.text_to_synthesize[:20]}...")
    
    def call(self, text):
        """调用 TTS"""
        self.audio_data = b''
        self.done.clear()
        self.error = None
        self.text_to_synthesize = text
        
        # 创建 WebSocket 连接（通过 header 传递 API Key）
        ws = websocket.WebSocketApp(
            self.ws_url,
            header={"Authorization": f"Bearer {self.api_key}"},
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # 运行 WebSocket（阻塞）
        ws.run_forever()
        
        # 等待完成或超时
        if not self.done.wait(timeout=30):
            self.error = "请求超时"
        
        if self.error:
            raise Exception(self.error)
        
        return self.audio_data
    
    def get_first_package_delay(self):
        if self.first_package_time and self.connection_start_time:
            return int((self.first_package_time - self.connection_start_time) * 1000)
        return 0
    
    def get_last_request_id(self):
        return self.request_id or "unknown"

# ============================================
# 主函数
# ============================================
def text_to_speech(text, output_path, voice=DEFAULT_VOICE, model=DEFAULT_MODEL):
    """文字转语音"""
    try:
        # 加载 API Key
        api_key = load_api_key()
        
        # 创建 TTS 调用器
        tts = CosyVoiceTTS(api_key=api_key, model=model, voice=voice)
        
        # 调用 API
        logger.info(f"正在生成语音...")
        audio_data = tts.call(text)
        
        # 保存到文件
        with open(output_path, 'wb') as f:
            f.write(audio_data)
        
        # 输出统计
        file_size = os.path.getsize(output_path)
        logger.info(f"✓ 语音生成成功")
        logger.info(f"  文件：{output_path} ({file_size} bytes)")
        logger.info(f"  Request ID: {tts.get_last_request_id()}")
        logger.info(f"  首包延迟：{tts.get_first_package_delay()}ms")
        
        return True, output_path
        
    except Exception as e:
        logger.error(f"✗ 转换失败：{e}")
        return False, str(e)

# ============================================
# 命令行入口
# ============================================
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法：python tts-official.py <文本> <输出文件>")
        print("示例：python tts-official.py '你好，我是小柔' /tmp/voice.mp3")
        sys.exit(1)
    
    text = sys.argv[1]
    output = sys.argv[2]
    
    success, message = text_to_speech(text, output)
    
    if success:
        print(f"✅ 语音生成成功：{output}")
        sys.exit(0)
    else:
        print(f"❌ 语音生成失败：{message}")
        sys.exit(1)
