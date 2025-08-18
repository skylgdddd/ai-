import warnings
from transformers import logging as transformers_logging
import threading
import queue
import time
import os
import sys

# 设置日志级别忽略未来警告
warnings.filterwarnings("ignore", category=FutureWarning)
transformers_logging.set_verbosity_error()

from utils.logger import logger
from config import Config
from memory_manager import MemoryManager
from subtitles import SubtitleManager

# 如果启用了TTS，导入TTS模块
if Config.ENABLE_TTS:
    from hewoyi_tts import HeWoYiTTS

# 命令常量
EXIT_CMD = "exit"
CLEAR_HISTORY_CMD = "/clear"
FORGET_MEMORY_CMD = "/forget"
TEST_SUBTITLE_CMD = "/testsubtitle"
RESET_SUBTITLE_CMD = "/resetsubtitle"
LIST_MEMORIES_CMD = "/listmem"
DELETE_MEMORY_CMD = "/delmem"
TOGGLE_PROGRAM_CMD = "/toggle_program"
TOGGLE_WEBSITE_CMD = "/toggle_website"
LIST_STATUS_CMD = "/list_status"

class InputThread(threading.Thread):
    """异步输入处理线程：只负责把终端输入放进队列"""
    def __init__(self, out_queue: queue.Queue):
        super().__init__(daemon=True)
        self._queue = out_queue
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                s = input()
            except EOFError:
                self._queue.put(None)
                break
            self._queue.put(s)

    def stop(self):
        self._stop.set()


class WorkerThread(threading.Thread):
    """
    工作线程：消费输入、处理命令、跑 LLM/TTS，并调用字幕显示。
    主线程只跑 pygame 渲染循环，避免"窗口无响应"。
    """
    def __init__(self, bot, in_queue: queue.Queue, run_event: threading.Event):
        super().__init__(daemon=True)
        self.bot = bot
        self.in_queue = in_queue
        self.run_event = run_event
        # 添加一个事件来同步启动
        self.ready_event = threading.Event()

    def run(self):
        # 等待主线程准备好后再打印提示
        self.ready_event.wait()
        print("You: ", end='', flush=True)
        while self.run_event.is_set():
            try:
                u = self.in_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if u is None:
                # 输入流结束
                self.run_event.clear()
                break

            cmd_result = self.bot.handle_command(u)
            if cmd_result is False:  # exit
                self.run_event.clear()
                break
            elif cmd_result is True:  # 命令已处理
                print("You: ", end='', flush=True)
                continue
            else:
                # 普通对话
                self.bot.process_user_input(u)
                print("You: ", end='', flush=True)


class AiChat:
    """主程序对象；字幕窗口/渲染在主线程，其他在工作线程。"""
    def __init__(self):
        # 运行控制 - 使用Event而不是Condition
        self.run_event = threading.Event()
        self.run_event.set()
        self._request_subtitle_reset = False
        self._subtitle_restart_count = 0  # 添加重启计数器

        # 长期记忆
        self.memory_manager = MemoryManager() if Config.ENABLE_LONG_TERM_MEMORY else None

        # 字幕管理器（主线程创建）
        self.subtitle_manager = None
        if Config.ENABLE_SUBTITLES:
            self._init_subtitles_mainthread()

        # LLM/TTS
        from llm import DeepSeekAPIModel
        if not Config.DEEPSEEK_API_KEY:
            raise ValueError("DeepSeek API密钥未配置")
        logger.info("使用DeepSeek API模型")
        self.llm = DeepSeekAPIModel(memory_manager=self.memory_manager)
        
        self.tts = HeWoYiTTS() if Config.ENABLE_TTS else None

        # 对话历史
        self.conversation_history = []

        logger.info("AiChat 实例已创建")

    # ---------------- 字幕（必须主线程） ----------------
    def _init_subtitles_mainthread(self):
        try:
            self.subtitle_manager = SubtitleManager(
                width=Config.SUBTITLE_WIDTH,
                height=Config.SUBTITLE_HEIGHT,
                fps=Config.SUBTITLE_FPS,
                frameless=Config.SUBTITLE_FRAMELESS,
                click_through=Config.SUBTITLE_CLICK_THROUGH,
                topmost=Config.SUBTITLE_TOPMOST,
                transparent=Config.SUBTITLE_TRANSPARENT
            )
            logger.info("字幕管理器已启用（使用配置参数初始化）")
        except Exception as e:
            logger.error(f"字幕系统初始化失败: {e}")
            self.subtitle_manager = None

    def _reset_subtitles_mainthread(self):
        """必须在主线程调用"""
        logger.warning("正在重启字幕系统...")
        try:
            if self.subtitle_manager:
                self.subtitle_manager.close()
        except Exception as e:
            logger.error(f"关闭字幕出错: {e}")
        
        time.sleep(0.2)
        self._init_subtitles_mainthread()

    # ---------------- 命令/对话 ----------------
    def _trim_history(self):
        max_length = Config.MAX_HISTORY_LENGTH * 2
        if len(self.conversation_history) > max_length:
            self.conversation_history = self.conversation_history[-max_length:]
            logger.info(f"已修剪对话历史至{max_length}条")

    def handle_command(self, cmd: str):
        if cmd is None:
            return False
            
        cmd = cmd.strip().lower()

        if cmd == EXIT_CMD:
            logger.info("用户退出程序")
            return False

        if cmd == CLEAR_HISTORY_CMD:
            self.conversation_history = []
            print("对话历史已清空")
            logger.info("用户清空对话历史")
            return True

        if cmd == FORGET_MEMORY_CMD and self.memory_manager:
            self.memory_manager = MemoryManager()
            print("长期记忆已清空")
            logger.info("用户清空长期记忆")
            return True
        
        if cmd.startswith(LIST_MEMORIES_CMD):
            try:
                parts = cmd.split()
                limit = 5
                if len(parts) > 1:
                    limit = int(parts[1])
                memories = self.memory_manager.list_memories(limit=limit)
                print(f"\n最近{len(memories)}条记忆:")
                for mem in memories:
                    print(f"  [{mem['id'][:8]}] {mem['text'][:60]}...")
            except Exception as e:
                print(f"列出记忆失败: {e}")
            return True
        
        if cmd.startswith(DELETE_MEMORY_CMD):
            try:
                parts = cmd.split()
                if len(parts) < 2:
                    print("使用方法: /delmem <记忆ID>")
                    return True
                
                memory_id = parts[1]
                if self.memory_manager.delete_memory(memory_id):
                    print(f"已删除记忆 {memory_id}")
                else:
                    print("未找到指定记忆")
            except Exception as e:
                print(f"删除记忆失败: {e}")
            return True

        if cmd == TEST_SUBTITLE_CMD and self.subtitle_manager:
            logger.info("用户触发字幕测试命令")
            self.subtitle_manager.show_subtitle("这是一个字幕测试，请检查字体、透明、穿透效果！")
            return True

        if cmd == RESET_SUBTITLE_CMD:
            logger.info("用户触发字幕重启命令")
            self._request_subtitle_reset = True
            return True
        
        # 添加开关控制命令
        if cmd.startswith(TOGGLE_PROGRAM_CMD):
            try:
                parts = cmd.split(maxsplit=2)
                if len(parts) < 3:
                    print("使用方法: /toggle_program <程序名> <on|off>")
                    return True
                
                program_name = parts[1]
                status = parts[2].lower() == "on"
                
                from action_manager import ActionManager
                if status:
                    result = ActionManager.toggle_program(program_name, True)
                else:
                    result = ActionManager.toggle_program(program_name, False)
                
                print(result)
            except Exception as e:
                print(f"切换程序状态失败: {e}")
            return True
        
        if cmd.startswith(TOGGLE_WEBSITE_CMD):
            try:
                parts = cmd.split(maxsplit=2)
                if len(parts) < 3:
                    print("使用方法: /toggle_website <网站名> <on|off>")
                    return True
                
                website_name = parts[1]
                status = parts[2].lower() == "on"
                
                from action_manager import ActionManager
                if status:
                    result = ActionManager.toggle_website(website_name, True)
                else:
                    result = ActionManager.toggle_website(website_name, False)
                
                print(result)
            except Exception as e:
                print(f"切换网站状态失败: {e}")
            return True
        
        if cmd == LIST_STATUS_CMD:
            from action_manager import ActionManager
            print(ActionManager.list_status())
            return True
        
        return None

    def process_user_input(self, user_input: str):
        try:
            logger.info(f"用户输入: {user_input}")
            response = self.llm.generate_response(user_input, self.conversation_history)

            print(f"Neuro-Sama: {response}")
            logger.info(f"Neuro-Sama 响应: {response}")

            # 并行处理TTS和字幕
            tts_success = False
            subtitle_success = False
            
            if self.tts:
                try:
                    self.tts.speak(response)
                    tts_success = True
                except Exception as e:
                    logger.error(f"TTS 播放失败: {e}")

            if self.subtitle_manager:
                try:
                    self.subtitle_manager.show_subtitle(response)
                    subtitle_success = True
                except Exception as e:
                    logger.error(f"显示字幕失败: {e}")

            # 记录对话
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response})

            # 长期记忆
            if self.memory_manager:
                try:
                    self.memory_manager.add_memory(f"用户说: {user_input}")
                    self.memory_manager.add_memory(f"Neuro-Sama 说: {response}")
                except Exception as e:
                    logger.error(f"添加长期记忆失败: {e}")

            self._trim_history()
            
            return tts_success and subtitle_success
        except Exception as e:
            logger.error(f"处理用户输入出错: {e}", exc_info=True)
            print(f"处理用户输入出错: {e}")
            return False

    # ---------------- 主线程渲染循环 ----------------
    def run_mainloop(self, worker: WorkerThread):
        """主线程：只负责渲染循环（pygame）"""
        try:
            # 启动横幅
            print("\n" + "="*50)
            print(f"=== AiChat 启动 {'(带TTS功能)' if Config.ENABLE_TTS else '(纯文本模式)'} ===")
            print(f"字幕功能: {'启用' if Config.ENABLE_SUBTITLES else '禁用'}")
            print(f"长期记忆: {'启用' if Config.ENABLE_LONG_TERM_MEMORY else '禁用'}")
            print(f"外部操作: {'启用' if Config.ENABLE_EXTERNAL_ACTIONS else '禁用'}")
            print("="*50)
            print(f"输入 '{EXIT_CMD}' 退出程序")
            print(f"输入 '{CLEAR_HISTORY_CMD}' 清空对话历史")
            if Config.ENABLE_LONG_TERM_MEMORY:
                print(f"输入 '{FORGET_MEMORY_CMD}' 清空长期记忆")
                print(f"输入 '{LIST_MEMORIES_CMD} [数量]' 列出最近的记忆")
                print(f"输入 '{DELETE_MEMORY_CMD} <记忆ID>' 删除指定记忆")
            if Config.ENABLE_SUBTITLES:
                print(f"输入 '{TEST_SUBTITLE_CMD}' 测试字幕显示")
                print(f"输入 '{RESET_SUBTITLE_CMD}' 重启字幕系统")
            if Config.ENABLE_EXTERNAL_ACTIONS:
                print(f"输入 '{TOGGLE_PROGRAM_CMD} <程序名> <on|off>' 切换程序状态")
                print(f"输入 '{TOGGLE_WEBSITE_CMD} <网站名> <on|off>' 切换网站状态")
                print(f"输入 '{LIST_STATUS_CMD}' 列出所有程序/网站状态")
            print("="*50 + "\n")
            
            # 通知工作线程可以开始打印提示了
            worker.ready_event.set()

            # 渲染主循环
            while self.run_event.is_set():
                # 处理字幕渲染
                if self.subtitle_manager and self.subtitle_manager.active:
                    try:
                        self.subtitle_manager.render()
                    except Exception as e:
                        logger.error(f"渲染字幕出错: {e}")
                        self._request_subtitle_reset = True
                
                # 处理字幕重启请求
                if self._request_subtitle_reset:
                    self._subtitle_restart_count += 1

                    # 限制重启次数，避免无限循环
                    if self._subtitle_restart_count > 5:
                        logger.error("字幕系统连续重启失败，已禁用字幕功能")
                        self.subtitle_manager = None
                    else:
                        logger.warning(f"尝试重启字幕系统 (尝试 #{self._subtitle_restart_count})")
                        self._reset_subtitles_mainthread()

                    self._request_subtitle_reset = False
                
                # 控制循环频率
                time.sleep(0.02 if self.subtitle_manager else 0.1)

        except KeyboardInterrupt:
            logger.warning("程序被键盘中断")
            self.run_event.clear()
        except Exception as e:
            logger.critical(f"主循环异常: {e}", exc_info=True)
            self.run_event.clear()
        finally:
            # 确保安全退出
            if self.subtitle_manager:
                try:
                    self.subtitle_manager.close()
                except Exception as e:
                    logger.error(f"关闭字幕失败: {e}")


def main():
    # 确保 stdout 为 UTF-8
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    bot = None
    input_thread = None
    worker = None
    
    try:
        bot = AiChat()

        # 准备输入队列与线程
        in_queue = queue.Queue()
        input_thread = InputThread(in_queue)
        input_thread.start()

        # 启动工作线程
        worker = WorkerThread(bot, in_queue, bot.run_event)
        worker.start()

        # 主线程只跑字幕渲染循环
        bot.run_mainloop(worker)

        print("程序退出中...")

    except Exception as e:
        logger.critical(f"程序初始化失败: {e}", exc_info=True)
        print(f"程序崩溃: {e}")
    finally:
        # 清理资源
        if bot and bot.run_event.is_set():
            bot.run_event.clear()
        
        if input_thread:
            input_thread.stop()
        
        # 等待线程结束
        if worker and worker.is_alive():
            worker.join(timeout=1.0)
        if input_thread and input_thread.is_alive():
            input_thread.join(timeout=0.5)
        
        logger.info("程序已退出")


if __name__ == '__main__':
    main()