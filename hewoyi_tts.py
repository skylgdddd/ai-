import requests
import re
import json
import os
import tempfile
import time
import subprocess
import threading
import urllib.parse
import logging
from config import Config
from utils.logger import logger

class HeWoYiTTS:
    def __init__(self):
        self.api_key = Config.HEWOYI_API_KEY
        self.voice = Config.HEWOYI_VOICE
        self.speed = Config.HEWOYI_SPEED
        self.tone = Config.HEWOYI_TONE
        self.format = Config.HEWOYI_FORMAT
        self.url = "https://api.hewoyi.com/api/ai/audio/speech"
        
        # 设置临时音频保存路径
        self.temp_audio_dir = r"D:\AI_Table_Pet_Programme\qwen_chat_project\temp_audio"
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        logger.info(f"临时音频文件将保存在: {self.temp_audio_dir}")
        
        # 验证配置
        if not self.api_key:
            logger.error("合我意API密钥未配置，无法使用TTS功能")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"合我意TTS已初始化，使用语音: {self.voice}")
            logger.info("API密钥验证成功")

    def speak(self, text: str):
        if not self.enabled:
            logger.error("TTS 功能未启用或初始化失败")
            return
            
        # 清理文本（移除表情符号等非语音字符）
        clean_text = ''.join(char for char in text if char.isprintable() and not char in ["😊", "😂", "😢", "🤔", "😠", "🎉", "❤️", "✨", "😮", "😍"])
        
        # 如果文本为空，则不处理
        if not clean_text.strip():
            logger.warning("传入文本为空，不进行语音合成")
            return
            
        # 构建查询参数 - 使用GET请求
        params = {
            "key": self.api_key,
            "text": clean_text,
            "type": "speech"  # 必需参数
        }
        
        # 添加可选参数（如果提供）
        if self.voice:
            params["voice"] = self.voice
        if self.format:
            params["format"] = self.format
        if self.speed:
            params["speed"] = self.speed
        if self.tone:
            params["tone"] = self.tone
        
        # 构建URL
        query_string = urllib.parse.urlencode(params)
        request_url = f"{self.url}?{query_string}"
        
        try:
            logger.info(f"请求合我意TTS: {clean_text[:50]}...")
            logger.debug(f"请求URL: {request_url}")
            
            # 第一步：请求API获取HTML页面
            response = requests.get(request_url, timeout=10)
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"API请求失败: 状态码={response.status_code}")
                return
                
            # 设置正确的编码
            response.encoding = "utf-8"
            html_content = response.text
            logger.debug(f"API返回HTML内容: {html_content[:200]}...")
            
            # 第二步：从HTML中解析真实音频URL
            match = re.search(r'src=["\'](https?://[^"\']+tjit\.net[^"\']+)["\']', html_content)
            if not match:
                logger.error("未找到音频地址，请检查HTML结构")
                return
                
            audio_url = match.group(1).replace("&amp;", "&")
            logger.info(f"真实音频地址: {audio_url}")
            
            # 第三步：下载真实音频
            audio_response = requests.get(audio_url, timeout=10)
            if audio_response.status_code != 200:
                logger.error(f"音频下载失败: 状态码={audio_response.status_code}")
                return
                
            # 检查音频内容是否有效
            if len(audio_response.content) < 1024:
                logger.error(f"音频内容过小，可能是错误响应: 大小={len(audio_response.content)}字节")
                return
                
            # 根据音频格式设置文件后缀（默认为mp3）
            suffix = f".{self.format}" if self.format else ".mp3"
            
            # 创建文件名（使用时间戳确保唯一性）
            timestamp = int(time.time() * 1000)
            filename = f"hewoyi_tts_{timestamp}{suffix}"
            temp_file_path = os.path.join(self.temp_audio_dir, filename)
            
            # 保存音频文件到指定目录
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(audio_response.content)
                logger.info(f"音频文件保存到: {temp_file_path}")

            # 使用系统默认播放器播放（异步）
            threading.Thread(target=self.play_audio, args=(temp_file_path,)).start()

        except Exception as e:
            logger.error(f"合我意TTS请求异常: {str(e)}", exc_info=True)

    def play_audio(self, file_path):
        """播放音频文件"""
        try:
            logger.info(f"尝试播放音频: {file_path}")
            
            # 根据操作系统选择播放命令
            if os.name == 'nt':  # Windows
                # 使用系统默认播放器
                os.startfile(file_path)
                logger.info("使用默认播放器打开音频文件")
            
            # 等待播放完成（简单实现）
            time.sleep(3)  # 假设最短播放时间3秒
        except Exception as e:
            logger.error(f"播放音频失败: {str(e)}", exc_info=True)
        finally:
            # 延迟删除临时文件
            time.sleep(5)  # 确保播放完成
            try:
                os.unlink(file_path)
                logger.info(f"已删除临时文件: {file_path}")
            except Exception as e:
                logger.error(f"删除临时文件失败: {str(e)}")