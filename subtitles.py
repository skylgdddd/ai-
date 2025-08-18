# subtitles.py
import os
import sys
import time
import pygame
import pygame.freetype
from collections import deque

from utils.logger import logger
from config import Config

# ---------- Windows 常量 ----------
IS_WIN = sys.platform.startswith("win")

# 导入ctypes用于DPI感知设置
if IS_WIN:
    import ctypes

# 使用 pywin32 实现窗口样式
if IS_WIN:
    try:
        import win32gui
        import win32con
        import win32api
        HAVE_PYWIN32 = True
    except ImportError:
        logger.error("pywin32 未安装，Windows 特有功能将不可用")
        HAVE_PYWIN32 = False
else:
    HAVE_PYWIN32 = False

# 使用 win32con 常量
GWL_EXSTYLE = win32con.GWL_EXSTYLE
WS_EX_LAYERED = win32con.WS_EX_LAYERED
WS_EX_TRANSPARENT = win32con.WS_EX_TRANSPARENT
LWA_COLORKEY = win32con.LWA_COLORKEY  # 使用色键透明
SWP_NOMOVE = win32con.SWP_NOMOVE
SWP_NOSIZE = win32con.SWP_NOSIZE
SWP_SHOWWINDOW = win32con.SWP_SHOWWINDOW
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

def _get_cfg(name, default):
    return getattr(Config, name, default)

def _parse_color(val, default=(255,0,255)):
    if isinstance(val, (tuple, list)) and len(val) == 3:
        return tuple(int(c) for c in val)
    if isinstance(val, str):
        try:
            parts = [int(x.strip()) for x in val.split(",")]
            if len(parts) == 3:
                return tuple(parts)
        except Exception:
            pass
    return default

# 逐帧 DEBUG 抽样
def _should_debug(frame_counter: int, every_n: int) -> bool:
    if every_n <= 0:
        return False
    return (frame_counter % every_n) == 0


class SubtitleManager:
    """
    改进版字幕管理，使用色键透明实现背景完全透明，字幕不透明
    """
    def __init__(self,
                 width=_get_cfg('SUBTITLE_WIDTH', 800),
                 height=_get_cfg('SUBTITLE_HEIGHT', 200),
                 fps=_get_cfg('SUBTITLE_FPS', 60),
                 frameless=_get_cfg('SUBTITLE_FRAMELESS', True),
                 click_through=_get_cfg('SUBTITLE_CLICK_THROUGH', True),
                 topmost=_get_cfg('SUBTITLE_TOPMOST', True),
                 transparent=_get_cfg('SUBTITLE_TRANSPARENT', True),
                 caption="Neuro-Sama Subtitles"):
        # 窗口与行为配置
        self.width  = int(width)
        self.height = int(height)
        self.fps    = int(fps)
        self.idle_fps = int(_get_cfg('SUBTITLE_IDLE_FPS', max(10, self.fps // 4)))
        self.caption = caption

        self.frameless      = bool(frameless)
        self.click_through  = bool(click_through)
        self.topmost        = bool(topmost)
        self.transparent    = bool(transparent)
        
        # 透明色键设置 - 使用配置中的透明颜色
        self.transparent_color = _parse_color(
            _get_cfg('SUBTITLE_TRANSPARENT_COLOR', (0, 0, 0)), 
            (0, 0, 0)  # 默认黑色
        )
        
        # 字体 & 效果配置
        self.font_name      = _get_cfg('SUBTITLE_FONT_NAME', 'Microsoft YaHei')
        self.font_size_base = int(_get_cfg('SUBTITLE_FONT_SIZE', 36))
        self.antialias = bool(_get_cfg('SUBTITLE_ANTIALIAS', False))  # 新增抗锯齿配置
        self.outline_color = _parse_color(
            _get_cfg('SUBTITLE_OUTLINE_COLOR', (0, 0, 0)), 
            (0, 0, 0)  # 默认黑色
        )
        self.outline_size = int(_get_cfg('SUBTITLE_OUTLINE_SIZE', 2))
        self.font_size      = self.font_size_base
        self.text_color     = _parse_color(
            _get_cfg('SUBTITLE_COLOR', (255, 255, 255)), 
            (255, 255, 255)
        )

        self.typing_speed       = float(_get_cfg('SUBTITLE_TYPING_SPEED', 0.15))   # s/char
        self.audio_char_time    = float(_get_cfg('SUBTITLE_AUDIO_CHAR_TIME', 0.2)) # s/char
        self.extra_display_time = float(_get_cfg('SUBTITLE_EXTRA_DISPLAY_TIME', 4.0))

        # 日志与 watchdog
        self.debug_verbose       = bool(_get_cfg('SUBTITLE_DEBUG_VERBOSE', False))
        self.log_every_n_frames  = int(_get_cfg('SUBTITLE_LOG_EVERY_N_FRAMES', 60))
        self.watchdog_timeout_s  = float(_get_cfg('SUBTITLE_WATCHDOG_TIMEOUT', 3.0))

        # 状态
        self.active = False
        self.queue = deque()         # (text, duration)
        self.current_subtitle = ""
        self.duration = 0.0
        self.show_time = 0.0

        # 逐帧 & 缓存
        self._frame_counter = 0
        self._last_flip_ts  = time.time()   # 最后一次 flip 成功时间
        self._last_render_ts= time.time()   # 最后一次 render 调用时间
        self.cached_lines = []
        self.cached_text_for_layout = None
        self.cached_width_for_layout = None
        self.cached_font_size_for_layout = None

        # 初始化 Pygame/窗口
        self._init_pygame_and_window()
        
        # +++ 启动时立即显示一个空白字幕 +++
        if self.active:
            self.show_subtitle(" ", duration=0.1)  # 显示一个空格字符，持续0.1秒

    # ---------- 初始化 ----------
    def _init_pygame_and_window(self):
        # DPI aware - 增强DPI感知设置
        if IS_WIN and HAVE_PYWIN32:
            try:
                # 尝试设置Per monitor DPI aware V2 (Windows 10 1703+)
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
                ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            except Exception:
                try:
                    # 回退到SetProcessDpiAwareness
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor DPI aware
                except Exception as e:
                    logger.warning(f"[SUBTITLE][DPI] 设置DPI感知失败: {e}")
        
        # 初始化Pygame
        try:
            pygame.init()
            pygame.freetype.init()
            flags = 0
            if self.frameless:
                flags |= pygame.NOFRAME
            
            # 创建窗口
            self.screen = pygame.display.set_mode((self.width, self.height), flags)
            pygame.display.set_caption(self.caption)
            self.clock = pygame.time.Clock()
            self.font = self._safe_font_load(self.font_size)
            
            # 立即应用Windows样式
            if IS_WIN:
                self._apply_windows_styles()
            
            # 设置窗口位置
            self._set_window_position()
            
            # 填充透明背景并刷新
            self.screen.fill(self.transparent_color)
            pygame.display.flip()
            
            # 添加第二次渲染确保样式生效 
            self.screen.fill(self.transparent_color)
            pygame.display.flip()
            
            self.active = True
            font_label = self.font_name if os.path.exists(self.font_name) else self.font.name if hasattr(self.font, "name") else self.font_name
            logger.info(
                f"[SUBTITLE] 初始化完成: size={self.width}x{self.height}, fps={self.fps}, "
                f"frameless={self.frameless}, click_through={self.click_through}, topmost={self.topmost}, "
                f"transparent={self.transparent}, transparent_color={self.transparent_color}, "
                f"font={font_label}@{self.font_size_base}, antialias={self.antialias}"
            )
        except Exception as e:
            logger.error(f"[SUBTITLE][INIT] 初始化失败: {e}", exc_info=True)
            self.active = False

    def _set_window_position(self):
        """设置窗口位置（底部居中）"""
        try:
            if IS_WIN and HAVE_PYWIN32:
                # 获取主显示器工作区尺寸（排除任务栏）
                sw = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                sh = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                pos_x = (sw - self.width) // 2
                pos_y = sh - self.height - 50  # 离底部50像素
                
                # 使用SDL设置窗口位置
                os.environ['SDL_VIDEO_WINDOW_POS'] = f'{pos_x},{pos_y}'
                
                # 直接设置窗口位置
                hwnd = pygame.display.get_wm_info().get("window")
                if hwnd:
                    win32gui.SetWindowPos(
                        hwnd, 
                        win32con.HWND_TOP,
                        pos_x, pos_y,
                        self.width, self.height,
                        win32con.SWP_SHOWWINDOW
                    )
            else:
                # 非Windows平台
                pygame.display.init()
                info = pygame.display.Info()
                sw, sh = info.current_w, info.current_h
                pos_x = (sw - self.width) // 2
                pos_y = sh - self.height - 50
                os.environ["SDL_VIDEO_WINDOW_POS"] = f"{pos_x},{pos_y}"
        except Exception as e:
            logger.warning(f"[SUBTITLE][POS] 设置窗口位置失败: {e}")

    def _apply_windows_styles(self):
        """
        使用 pywin32 设置窗口样式（使用色键透明）
        """
        if not (IS_WIN and HAVE_PYWIN32 and self.active):
            return
            
        try:
            # 获取窗口句柄并重试
            hwnd = None
            for _ in range(10):  # 最多重试10次
                try:
                    hwnd = pygame.display.get_wm_info().get("window")
                    if hwnd:
                        break
                except Exception:
                    pass
                time.sleep(0.1)
            
            if not hwnd:
                logger.warning("无法获取窗口句柄")
                return
            
            # 设置窗口样式
            exstyle = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
            new_exstyle = int(exstyle)
            
            # 启用分层窗口（必须）
            new_exstyle |= WS_EX_LAYERED
            
            # 设置鼠标穿透
            if self.click_through:
                new_exstyle |= WS_EX_TRANSPARENT
            else:
                new_exstyle &= ~WS_EX_TRANSPARENT
            
            # 应用新样式
            if new_exstyle != exstyle:
                win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, new_exstyle)
            
            # 设置透明色键
            try:
                r, g, b = self.transparent_color
                colorref = win32api.RGB(r, g, b)
                win32gui.SetLayeredWindowAttributes(hwnd, colorref, 0, LWA_COLORKEY)
            except Exception as e:
                logger.warning(f"[SUBTITLE][STYLE] 设置色键透明失败: {e}")
            
            # 设置窗口置顶
            if self.topmost:
                win32gui.SetWindowPos(
                    hwnd, HWND_TOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                )
            else:
                win32gui.SetWindowPos(
                    hwnd, HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                )
            
            # 强制重绘窗口
            win32gui.RedrawWindow(
                hwnd, 
                None, 
                None, 
                win32con.RDW_ERASE | win32con.RDW_FRAME | win32con.RDW_INVALIDATE | win32con.RDW_ALLCHILDREN
            )
        
        except Exception as e:
            logger.warning(f"[SUBTITLE][STYLE] 设置窗口样式失败: {e}")

    # ---------- 字体 ----------
    def _safe_font_load(self, size: int):
        # 优先使用字体文件路径
        try:
            if isinstance(self.font_name, str) and os.path.exists(self.font_name):
                # 使用指定抗锯齿设置
                font = pygame.freetype.Font(self.font_name, size)
                font.antialiased = self.antialias
                logger.info(f"[FONT] 加载字体文件: {self.font_name}, 抗锯齿: {self.antialias}")
                return font
        except Exception as e:
            logger.warning(f"[FONT] 加载字体文件失败: {self.font_name}, {e}")
        
        # 尝试系统字体
        try:
            ft = pygame.freetype.SysFont(self.font_name, size)
            ft.antialiased = self.antialias
            # 简单中文探测
            surf, _ = ft.render("中文测试", (255,255,255))
            if surf.get_width() > 8:
                logger.info(f"[FONT] 使用系统字体: {self.font_name}, 抗锯齿: {self.antialias}")
                return ft
        except Exception as e:
            logger.warning(f"[FONT] 加载系统字体失败: {self.font_name}, {e}")
        
        # 回退
        for fallback in ("Microsoft YaHei", "SimHei", "SimSun", "Arial"):
            try:
                ft = pygame.freetype.SysFont(fallback, size)
                ft.antialiased = self.antialias
                surf, _ = ft.render("中文测试", (255,255,255))
                if surf.get_width() > 8:
                    logger.warning(f"[SUBTITLE][FONT] 使用回退字体: {fallback}, 抗锯齿: {self.antialias}")
                    return ft
            except Exception as e:
                logger.warning(f"[FONT] 加载回退字体失败: {fallback}, {e}")
                continue
        logger.warning("[SUBTITLE][FONT] 使用默认字体")
        return pygame.freetype.Font(None, size)

    # ---------- 文本 API ----------
    def _clean_text(self, s: str) -> str:
        return s or ""

    def show_subtitle(self, text: str, duration: float = None):
        """入队字幕；duration=None 则按字符时长估算"""
        if not self.active:
            return
        t = self._clean_text(str(text))
        if duration is None:
            typing_t = len(t) * max(self.typing_speed, 0.0)
            audio_t  = len(t) * max(self.audio_char_time, 0.0)
            duration = max(typing_t, audio_t) + max(self.extra_display_time, 0.0)
        self.queue.append((t, float(duration)))
        logger.info(f"[QUEUE] 入队字幕 len={len(t)} dur={duration:.2f}s; 队列={len(self.queue)}")

    # ---------- 事件处理 ----------
    def _process_events(self):
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.close()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.close()
        except Exception as e:
            logger.warning(f"[SUBTITLE][EVENT] 事件处理异常: {e}")

    # ---------- 布局 / 字体自适应 ----------
    def _text_width(self, s: str) -> int:
        try:
            rect = self.font.get_rect(s)
            return rect.width
        except Exception:
            return len(s) * max(self.font_size // 2, 8)

    def _recalc_layout_if_needed(self, text: str):
        if (text == self.cached_text_for_layout and
            self.width == self.cached_width_for_layout and
            self.font_size == self.cached_font_size_for_layout):
            return
        lines = []
        line = ""
        limit = self.width - 20
        for ch in text:
            if self._text_width(line + ch) > limit:
                lines.append(line)
                line = ch
            else:
                line += ch
        if line:
            lines.append(line)
        self.cached_lines = lines
        self.cached_text_for_layout = text
        self.cached_width_for_layout = self.width
        self.cached_font_size_for_layout = self.font_size

    def _adjust_font_size_if_needed(self, text: str):
        if not text:
            return
        self._recalc_layout_if_needed(text)
        line_h = self.font_size + 4
        required_h = len(self.cached_lines) * line_h
        if required_h <= self.height:
            return
        new_size = self.font_size
        while required_h > self.height and new_size > 12:
            new_size -= 2
            if new_size == self.font_size:
                break
            self.font_size = new_size
            self.font = self._safe_font_load(self.font_size)
            self._recalc_layout_if_needed(text)
            line_h = self.font_size + 4
            required_h = len(self.cached_lines) * line_h

    # ---------- Watchdog ----------
    def _watchdog_check(self):
        now = time.time()
        # 若 flip 太久没有成功（>timeout），尝试自我重启
        if now - self._last_flip_ts > self.watchdog_timeout_s:
            logger.warning(f"[SUBTITLE][WATCHDOG] {self.watchdog_timeout_s:.1f}s 未刷新，触发自我重启")
            self._safe_restart()

    def _safe_restart(self):
        """保留队列和当前字幕，重新初始化窗口/样式"""
        try:
            # 记录当前状态
            saved_queue = deque(self.queue)
            saved_current = self.current_subtitle
            saved_duration = self.duration
            elapsed = max(0.0, time.time() - self.show_time) if self.current_subtitle else 0.0

            # 关闭现有窗口
            try:
                pygame.display.quit()
            except Exception:
                pass
            try:
                pygame.quit()
            except Exception:
                pass
            time.sleep(0.15)

            # 重新初始化
            self.active = False
            self._init_pygame_and_window()
            
            # +++ 重启后也显示一个空白字幕 +++
            if self.active:
                self.show_subtitle(" ", duration=0.1)

            # 恢复状态
            if self.active:
                self.queue = saved_queue
                self.current_subtitle = saved_current
                self.duration = saved_duration
                # show_time 重新计算：避免立刻结束
                if self.current_subtitle:
                    self.show_time = time.time() - min(elapsed, max(self.duration - 0.5, 0.0))
                logger.info("[SUBTITLE][WATCHDOG] 重启完成")
        except Exception as e:
            logger.error(f"[SUBTITLE][WATCHDOG] 重启失败: {e}", exc_info=True)

    # ---------- 渲染主函数 ----------
    def render(self):
        if not self.active:
            return

        self._frame_counter += 1
        self._last_render_ts = time.time()

        # 抽样 DEBUG
        if self.debug_verbose and _should_debug(self._frame_counter, self.log_every_n_frames):
            logger.debug(f"[RENDER] 帧={self._frame_counter} 当前字幕len={len(self.current_subtitle)} 队列={len(self.queue)}")

        # 事件
        self._process_events()

        # 取新字幕
        if not self.current_subtitle and self.queue:
            self.current_subtitle, self.duration = self.queue.popleft()
            self.show_time = time.time()
            # 恢复基础字体大小
            if self.font_size != self.font_size_base:
                self.font_size = self.font_size_base
                self.font = self._safe_font_load(self.font_size)
            # 清布局缓存
            self.cached_text_for_layout = None
            logger.info(f"[PLAY] 取出新字幕 len={len(self.current_subtitle)} dur={self.duration:.2f}s; 队列剩余={len(self.queue)}")

        # 无字幕：清屏 + 降频
        if not self.current_subtitle:
            # 使用透明色填充背景
            self.screen.fill(self.transparent_color)
            try:
                pygame.display.flip()
            except Exception:
                pass
            self._last_flip_ts = time.time()
            self.clock.tick(self.idle_fps)
            # watchdog（空闲时也需要检测）
            self._watchdog_check()
            return

        # 打字机
        elapsed = time.time() - self.show_time
        if self.typing_speed > 0:
            visible_chars = min(len(self.current_subtitle), int(elapsed / self.typing_speed))
        else:
            visible_chars = len(self.current_subtitle)
        draw_text = self.current_subtitle[:visible_chars]

        # 字体自适应（必要时）
        self._adjust_font_size_if_needed(draw_text)
        self._recalc_layout_if_needed(draw_text)

        # 绘制
        # 1. 用透明色填充整个背景
        self.screen.fill(self.transparent_color)
        
        # 2. 绘制不透明的字幕文本
        total_h = len(self.cached_lines) * (self.font_size + 4)
        y = (self.height - total_h) // 2
        for line in self.cached_lines:
            try:
                # 渲染轮廓（如果启用）
                if self.outline_size > 0:
                    # 创建轮廓效果 - 在多个偏移位置渲染文本
                    for dx in range(-self.outline_size, self.outline_size + 1):
                        for dy in range(-self.outline_size, self.outline_size + 1):
                            if dx != 0 or dy != 0:  # 跳过中心位置
                                outline_surf, outline_rect = self.font.render(
                                    line,
                                    self.outline_color
                                )
                                outline_rect.centerx = self.width // 2 + dx
                                outline_rect.top = y + dy
                                self.screen.blit(outline_surf, outline_rect)
                # 渲染主文本
                text_surf, text_rect = self.font.render(
                    line,
                    self.text_color
                )
                text_rect.centerx = self.width // 2
                text_rect.top = y
                self.screen.blit(text_surf, text_rect)

            except Exception as e:
                logger.error(f"[SUBTITLE][DRAW] 渲染行失败: {e}")
            y += self.font_size + 4    

        # 尝试翻转显示
        try:
            pygame.display.flip()
            self._last_flip_ts = time.time()  # 更新翻转时间戳
        except Exception as e:
            logger.error(f"[SUBTITLE][FLIP] 翻转失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[SUBTITLE][RENDER] 渲染失败: {e}", exc_info=True)
            self._request_restart = True  # 标记需要重启                  

        # 关键：每帧强制重新应用窗口样式（确保置顶/穿透持续生效）
        if IS_WIN and HAVE_PYWIN32:
            self._apply_windows_styles()

        # 正常帧率
        self.clock.tick(self.fps)

        # 完成判断：文字打完 + 总时长到期
        total_need = self.duration
        if visible_chars >= len(self.current_subtitle) and elapsed >= total_need:
            logger.info("[PLAY] 当前字幕播放完毕")
            self.current_subtitle = ""
            self.cached_text_for_layout = None
            self.cached_lines = []

        # watchdog
        self._watchdog_check()

    # ---------- 关闭 ----------
    def close(self):
        if not self.active:
            return
        self.active = False
        try:
            pygame.display.quit()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass
        logger.info("[SUBTITLE] 已关闭")