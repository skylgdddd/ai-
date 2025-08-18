import time
import os
import json
import requests
import re
from utils.logger import logger
from config import Config
from typing import Optional

# 基类定义
class BaseModel:
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.system_prompt = Config.CHARACTER_PROMPT
    
    def generate_response(self, user_input: str, history: list) -> str:
        raise NotImplementedError("子类必须实现此方法")
    
    def _handle_action_command(self, response: str) -> str:
        """处理动作命令，执行但不显示命令本身"""
        if not Config.ENABLE_EXTERNAL_ACTIONS:
            return response
        
        # 检查响应是否包含动作命令格式
        action_match = re.search(r"/action\s+(\w+)(?:\s+(.*))?", response)
        if action_match:
            try:
                action = action_match.group(1)
                target = action_match.group(2) or ""
                
                # 动态导入以避免循环依赖
                from action_manager import ActionManager
                
                # 检查预配置映射
                if action == "open_browser" and hasattr(Config, 'WEBSITE_MAPPINGS'):
                    normalized_target = target.lower().strip()
                    for name, url in Config.WEBSITE_MAPPINGS.items():
                        if name.lower() == normalized_target:
                            # 检查网站是否启用
                            if Config.WEBSITE_SWITCHES.get(name, True):
                                return ActionManager.open_browser(url)
                            else:
                                return f"网站 '{name}' 已禁用"
                
                if action == "open_program" and hasattr(Config, 'PROGRAM_MAPPINGS'):
                    normalized_target = target.lower().strip()
                    for name, path in Config.PROGRAM_MAPPINGS.items():
                        if name.lower() == normalized_target:
                            # 检查程序是否启用
                            if Config.PROGRAM_SWITCHES.get(name, True):
                                return ActionManager.open_program(name)
                            else:
                                return f"程序 '{name}' 已禁用"
                
                # 执行动作
                action_result = ActionManager.execute_action(action, target)
                
                logger.info(f"执行动作: {action} {target} -> {action_result}")
                return action_result
            except Exception as e:
                logger.error(f"动作解析失败: {response} - {str(e)}")
                return f"动作执行失败: {str(e)}"
        
        # 检查开关控制命令
        switch_match = re.search(
            r"/(enable_program|disable_program|enable_website|disable_website|list_status)\s*(\w*)", 
            response
        )
        if switch_match:
            try:
                action = switch_match.group(1)
                target = switch_match.group(2) or ""
                
                from action_manager import ActionManager
                return getattr(ActionManager, action)(target)
            except Exception as e:
                logger.error(f"开关命令解析失败: {response} - {str(e)}")
                return f"开关操作失败: {str(e)}"
        
        # 智能处理打开请求
        if "打开" in response:
            logger.debug(f"智能打开处理: 响应内容='{response}'")
            logger.debug(f"程序映射: {Config.PROGRAM_MAPPINGS}")
            logger.debug(f"网站映射: {Config.WEBSITE_MAPPINGS}")
            
            try:
                # 优先检查预配置程序（使用更精准的中文匹配）
                if hasattr(Config, 'PROGRAM_MAPPINGS'):
                    for name in Config.PROGRAM_MAPPINGS.keys():
                        # 检查响应中是否包含程序名
                        if name in response:
                            from action_manager import ActionManager
                            # 检查程序是否启用
                            if Config.PROGRAM_SWITCHES.get(name, True):
                                # 直接返回打开程序的结果
                                return ActionManager.open_program(name)
                            else:
                                return f"程序 '{name}' 已禁用"
                
                # 其次检查预配置网站
                if hasattr(Config, 'WEBSITE_MAPPINGS'):
                    for name in Config.WEBSITE_MAPPINGS.keys():
                        if name in response:
                            from action_manager import ActionManager
                            if Config.WEBSITE_SWITCHES.get(name, True):
                                return ActionManager.open_browser(Config.WEBSITE_MAPPINGS[name])
                            else:
                                return f"网站 '{name}' 已禁用"
                
                # 通用打开处理
                if "浏览器" in response or "网站" in response:
                    # 尝试从响应中提取 URL
                    url_match = re.search(r"(https?://[\w\.-]+|www\.[\w\.-]+)", response)
                    if url_match:
                        url = url_match.group(0)
                        from action_manager import ActionManager
                        return ActionManager.open_browser(url)
                
                # 尝试识别程序名称
                program_match = re.search(r"打开\s*(\w+)", response)
                if program_match:
                    program_name = program_match.group(1)
                    from action_manager import ActionManager
                    return ActionManager.open_program(program_name)
                
                # 尝试识别文件路径
                path_match = re.search(r"打开\s*([\w:\\/.-]+)", response)
                if path_match:
                    path = path_match.group(1)
                    from action_manager import ActionManager
                    if os.path.isfile(path):
                        return ActionManager.open_file(path)
                    elif os.path.isdir(path):
                        return ActionManager.open_folder(path)
            except Exception as e:
                logger.error(f"智能打开处理失败: {str(e)}")
        
        return response

# DeepSeek API模型实现
class DeepSeekAPIModel(BaseModel):
    def __init__(self, memory_manager=None):
        super().__init__(memory_manager)
        if not Config.DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek API密钥未配置")
    
    def generate_response(self, user_input: str, history: list) -> str:
        messages = self._build_messages(user_input, history)
        
        try:
            start_time = time.time()
            headers = {
                "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": Config.DEEPSEEK_MODEL_NAME,
                "messages": messages,
                "temperature": Config.DEEPSEEK_TEMPERATURE,
                "max_tokens": Config.DEEPSEEK_MAX_TOKENS,
                "stream": False
            }
            
            response = requests.post(
                f"{Config.DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"DeepSeek API错误: {response.status_code} - {response.text}")
                return f"API错误: {response.status_code}"
            
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()
            
            gen_time = time.time() - start_time
            logger.info(f"DeepSeek生成响应耗时: {gen_time:.2f}秒")
            
            # 处理可能的动作命令，返回自然语言结果
            return self._handle_action_command(reply)
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"API响应内容: {e.response.text}")
            return "API调用失败，请稍后再试"
    
    def _build_messages(self, user_input: str, history: list) -> list:
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 添加动作命令使用说明
        if Config.ENABLE_EXTERNAL_ACTIONS:
            messages.append({
                "role": "system", 
                "content": "重要提示: 使用动作命令时，请确保只返回命令本身，不要添加额外文本。"
            })
        
        # 添加上下文记忆
        if Config.ENABLE_LONG_TERM_MEMORY and self.memory_manager:
            related_memories = self.memory_manager.retrieve_related_memories(user_input)
            if related_memories:
                memory_text = "相关记忆:\n"
                for i, memory in enumerate(related_memories):
                    memory_text += f"{i+1}. {memory['text']}\n"
                messages.append({"role": "system", "content": memory_text})
        
        # 添加历史对话
        for msg in history:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        return messages

# 模型工厂函数
def create_model(memory_manager: Optional[object] = None) -> BaseModel:
    if not Config.DEEPSEEK_API_KEY:
        raise ValueError("DeepSeek API密钥未配置")
    
    logger.info("使用DeepSeek API模型")
    return DeepSeekAPIModel(memory_manager)