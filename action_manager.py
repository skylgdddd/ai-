import os
import subprocess
import webbrowser
import re
import json
from config import Config
from utils.logger import logger
import urllib.parse

class ActionManager:
    @staticmethod
    def execute_action(action: str, target: str = "") -> str:
        """执行外部操作并返回结果消息"""
        if not Config.ENABLE_EXTERNAL_ACTIONS:
            return "外部操作功能已禁用"
        
        if action not in Config.ALLOWED_ACTIONS:
            return f"操作 '{action}' 未被允许"
        
        try:
            if action == "open_browser":
                # 检查网站是否启用
                if hasattr(Config, 'WEBSITE_SWITCHES'):
                    normalized_target = target.lower().strip()
                    for name in Config.WEBSITE_SWITCHES.keys():
                        if name.lower() == normalized_target:
                            if not Config.WEBSITE_SWITCHES.get(name, True):
                                return f"网站 '{name}' 已禁用"
                            # 使用映射的URL
                            return ActionManager.open_browser(Config.WEBSITE_MAPPINGS[name])
                
                return ActionManager.open_browser(target)
            
            elif action == "open_calculator":
                return ActionManager.open_calculator()
            
            elif action == "open_program":
                # 检查程序是否启用
                if hasattr(Config, 'PROGRAM_SWITCHES'):
                    normalized_target = target.lower().strip()
                    for name in Config.PROGRAM_SWITCHES.keys():
                        if name.lower() == normalized_target:
                            if not Config.PROGRAM_SWITCHES.get(name, True):
                                return f"程序 '{name}' 已禁用"
                
                return ActionManager.open_program(target)
            
            elif action == "open_file":
                return ActionManager.open_file(target)
            
            elif action == "open_folder":
                return ActionManager.open_folder(target)
            
            # 添加开关控制命令
            elif action == "enable_program":
                return ActionManager.toggle_program(target, True)
            elif action == "disable_program":
                return ActionManager.toggle_program(target, False)
            elif action == "enable_website":
                return ActionManager.toggle_website(target, True)
            elif action == "disable_website":
                return ActionManager.toggle_website(target, False)
            elif action == "list_status":
                return ActionManager.list_status()
            else:
                return f"未知操作: {action}"
        except Exception as e:
            logger.error(f"执行操作失败: {action} {target} - {str(e)}")
            return f"操作失败: {str(e)}"

    @staticmethod
    def open_browser(target: str = "https://cn.bing.com") -> str:
        """打开浏览器并清理 URL，支持搜索功能"""
        # 首先检查预配置网站
        if hasattr(Config, 'WEBSITE_SWITCHES'):
            normalized_target = target.lower().strip()
            for name in Config.WEBSITE_SWITCHES.keys():
                if name.lower() == normalized_target:
                    if not Config.WEBSITE_SWITCHES.get(name, True):
                        return f"网站 '{name}' 已禁用"
                    # 使用映射的URL
                    return ActionManager.open_browser(Config.WEBSITE_MAPPINGS[name])
        
        # 清理 target 格式
        target = target.replace("[", "").replace("]", "").strip()
        
        # 新增：判断是否是搜索查询
        is_search_query = ' ' in target or (not target.startswith(('http://', 'https://')) and '.' not in target)
        
        # 构造最终URL
        if is_search_query:
            # 使用默认搜索引擎
            search_engine = Config.DEFAULT_SEARCH_ENGINE
            # URL编码搜索词
            url = search_engine.replace('{search}', urllib.parse.quote(target))
        else:
            url = target
        
        # 如果 URL 包含多个协议，保留最外层的一个
        if url.startswith("http://http://") or url.startswith("https://https://"):
            url = url[url.find("//")+2:]
        
        # 确保以 https:// 开头
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        # 移除重复协议
        if url.startswith("https://https://"):
            url = "https://" + url[len("https://https://"):]
        elif url.startswith("http://http://"):
            url = "http://" + url[len("http://http://"):]
        
        # 提取域名用于自然语言显示
        domain_match = re.search(r"https?://([\w.-]+)", url)
        domain = domain_match.group(1) if domain_match else "网页"
        
        try:
            # 尝试使用系统默认浏览器
            webbrowser.open(url)
            return f"正在搜索: {target}" if is_search_query else f"已打开浏览器访问 {domain}"
        except:
            # 回退到直接调用浏览器程序
            if Config.BROWSER_PATH:
                subprocess.Popen([Config.BROWSER_PATH, url])
            else:
                subprocess.Popen(f"start {url}", shell=True)
            return f"正在搜索: {target}" if is_search_query else f"已启动浏览器访问 {domain}"

    @staticmethod
    def open_calculator() -> str:
        """打开计算器程序"""
        try:
            if os.name == 'nt':  # Windows
                subprocess.Popen('calc.exe')
                return "已打开计算器"
            else:  # Linux/Mac
                subprocess.Popen(['gnome-calculator'])  # Linux GNOME
                return "已打开计算器"
        except Exception as e:
            logger.error(f"打开计算器失败: {str(e)}")
            return "无法打开计算器"
    
    @staticmethod
    def open_program(program_name: str) -> str:
        """打开指定名称的程序"""
        # 修复：使用 PROGRAM_MAPPINGS 而不是 ALLOWED_PROGRAMS
        program_path = Config.PROGRAM_MAPPINGS.get(program_name.lower())
        
        if not program_path:
            # 尝试在程序映射中查找（使用原始名称）
            program_path = Config.PROGRAM_MAPPINGS.get(program_name)
            if not program_path:
                return f"未配置程序 '{program_name}'"
        
        try:
            # 检查路径是否有效
            if os.path.exists(program_path):
                # 使用 shell=True 确保可以打开带空格路径的程序
                subprocess.Popen(program_path, shell=True)
                return f"已打开程序: {program_name}"
            else:
                # 尝试使用系统路径查找
                subprocess.Popen(program_name, shell=True)
                return f"正在尝试打开: {program_name}"
        except Exception as e:
            logger.error(f"打开程序失败: {program_name} - {str(e)}")
            return f"无法打开程序: {program_name} ({str(e)})"
    
    @staticmethod
    def open_file(file_path: str) -> str:
        """打开指定文件"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"文件不存在: {file_path}"
            
            # 使用系统默认程序打开文件
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            else:  # Mac/Linux
                subprocess.Popen(['xdg-open', file_path])
            
            return f"已打开文件: {os.path.basename(file_path)}"
        except Exception as e:
            logger.error(f"打开文件失败: {file_path} - {str(e)}")
            return f"无法打开文件: {os.path.basename(file_path)}"
    
    @staticmethod
    def open_folder(folder_path: str) -> str:
        """打开指定文件夹"""
        try:
            # 检查文件夹是否存在
            if not os.path.exists(folder_path):
                return f"文件夹不存在: {folder_path}"
            
            # 打开文件夹
            if os.name == 'nt':  # Windows
                subprocess.Popen(f'explorer "{folder_path}"', shell=True)
            elif os.name == 'posix':  # Mac/Linux
                subprocess.Popen(['xdg-open', folder_path])
            
            return f"已打开文件夹: {os.path.basename(folder_path)}"
        except Exception as e:
            logger.error(f"打开文件夹失败: {folder_path} - {str(e)}")
            return f"无法打开文件夹: {os.path.basename(folder_path)}"
    
    @staticmethod
    def toggle_program(program_name: str, enable: bool) -> str:
        """切换程序开关状态"""
        if program_name not in Config.PROGRAM_MAPPINGS:
            return f"未配置程序: {program_name}"
        
        Config.PROGRAM_SWITCHES[program_name] = enable
        status = "开启" if enable else "关闭"
        return f"已{status}程序: {program_name}"
    
    @staticmethod
    def toggle_website(website_name: str, enable: bool) -> str:
        """切换网站开关状态"""
        if website_name not in Config.WEBSITE_MAPPINGS:
            return f"未配置网站: {website_name}"
        
        Config.WEBSITE_SWITCHES[website_name] = enable
        status = "开启" if enable else "关闭"
        return f"已{status}网站: {website_name}"
    
    @staticmethod
    def list_status() -> str:
        """列出所有程序/网站状态"""
        result = "当前状态:\n"
        
        if Config.PROGRAM_MAPPINGS:
            result += "\n程序状态:\n"
            for name in Config.PROGRAM_MAPPINGS.keys():
                status = "开" if Config.PROGRAM_SWITCHES.get(name, True) else "关"
                result += f"  - {name}: {status}\n"
        
        if Config.WEBSITE_MAPPINGS:
            result += "\n网站状态:\n"
            for name in Config.WEBSITE_MAPPINGS.keys():
                status = "开" if Config.WEBSITE_SWITCHES.get(name, True) else "关"
                result += f"  - {name}: {status}\n"
        
        return result.strip()