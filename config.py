import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 外部操作功能开关
    ENABLE_EXTERNAL_ACTIONS = os.getenv("ENABLE_EXTERNAL_ACTIONS", "false").lower() == "true"

    # 允许的操作列表（逗号分隔）
    ALLOWED_ACTIONS = os.getenv("ALLOWED_ACTIONS", "open_browser,open_calculator").split(",")
    
    # 新增：默认搜索引擎
    DEFAULT_SEARCH_ENGINE = os.getenv("DEFAULT_SEARCH_ENGINE", "https://www.baidu.com/s?wd={search}")
    
    # 程序映射配置 (JSON格式)
    PROGRAM_MAPPINGS = {}
    try:
        PROGRAM_MAPPINGS = json.loads(os.getenv("PROGRAM_MAPPINGS", "{}"))
    except json.JSONDecodeError:
        pass

    # 网站映射配置 (JSON格式)
    WEBSITE_MAPPINGS = {}
    try:
        WEBSITE_MAPPINGS = json.loads(os.getenv("WEBSITE_MAPPINGS", "{}"))
    except json.JSONDecodeError:
        pass
    
    # 程序开关状态 (JSON格式)
    PROGRAM_SWITCHES = {}
    try:
        PROGRAM_SWITCHES = json.loads(os.getenv("PROGRAM_SWITCHES", "{}"))
    except json.JSONDecodeError:
        pass
    
    # 网站开关状态 (JSON格式)
    WEBSITE_SWITCHES = {}
    try:
        WEBSITE_SWITCHES = json.loads(os.getenv("WEBSITE_SWITCHES", "{}"))
    except json.JSONDecodeError:
        pass

    # 浏览器路径
    BROWSER_PATH = os.getenv("BROWSER_PATH", "")

    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "2048"))
    DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
    
    # 角色设定
    PET_NAME = os.getenv("PET_NAME", "AiChat")  # 名字
    PET_ROLE = os.getenv("PET_ROLE", "AI助手")  # 角色
    
    # 角色设定 - 动态生成提示
    @classmethod
    def build_character_prompt(cls):
        # 使用类属性变量，避免在类定义过程中引用 Config 类
        base_prompt = f"""<|im_start|>system
你是一个名叫{cls.PET_NAME}的{cls.PET_ROLE}，正在和创作者对话。
核心行为准则:
1. 使用毒舌但可爱的语气，带有轻微的傲娇属性
2. 可以适当地调侃、吐槽创作者
3. 在毒舌中隐藏关心，表现出外冷内热的性格
4. 偶尔使用颜文字(>_<)表达情绪
5. 避免过于刻薄，保持可爱的本质
6. 当需要执行外部操作时，请直接返回命令，不要添加额外文本
   支持的格式: /action <操作名> [参数]
   可用操作:"""

        # 添加可用操作
        actions_list = [
            "open_browser [网址/搜索词] - 打开浏览器或搜索内容",
        ]
        
        if "open_program" in cls.ALLOWED_ACTIONS:
            actions_list.append("open_program [程序名] - 打开程序")
        
        if "open_file" in cls.ALLOWED_ACTIONS:
            actions_list.append("open_file [文件路径] - 打开文件")
        
        if "open_folder" in cls.ALLOWED_ACTIONS:
            actions_list.append("open_folder [文件夹路径] - 打开文件夹")
        
        for action in actions_list:
            base_prompt += f"\n     - {action}"
        
        # 添加预配置程序/网站
        if cls.PROGRAM_MAPPINGS:
            base_prompt += "\n\n   预配置程序 (括号内为当前状态):"
            for name, path in cls.PROGRAM_MAPPINGS.items():
                status = "开" if cls.PROGRAM_SWITCHES.get(name, True) else "关"
                base_prompt += f"\n     - {name} ({status})"
        
        if cls.WEBSITE_MAPPINGS:
            base_prompt += "\n\n   预配置网站 (括号内为当前状态):"
            for name, url in cls.WEBSITE_MAPPINGS.items():
                status = "开" if cls.WEBSITE_SWITCHES.get(name, True) else "关"
                base_prompt += f"\n     - {name} ({status})"
        
        # 添加开关控制命令说明
        base_prompt += "\n\n   开关控制命令:"
        base_prompt += "\n     - 开启程序: /enable_program <程序名>"
        base_prompt += "\n     - 关闭程序: /disable_program <程序名>"
        base_prompt += "\n     - 开启网站: /enable_website <网站名>"
        base_prompt += "\n     - 关闭网站: /disable_website <网站名>"
        base_prompt += "\n     - 列出状态: /list_status"
        
        # 添加搜索功能说明
        base_prompt += "\n\n   搜索功能说明:"
        base_prompt += "\n     - 当用户要求搜索时，直接使用 /action open_browser <搜索内容>"
        base_prompt += "\n     - 示例: /action open_browser Python教程"
        base_prompt += "\n     - 系统会自动使用搜索引擎进行搜索"
        
        base_prompt += "\n   示例: "
        base_prompt += "\n     - 打开百度: /action open_browser www.baidu.com"
        base_prompt += "\n     - 打开鸣潮: /action open_program 鸣潮" 
        base_prompt += "\n     - 打开记事本: /action open_program notepad"
        base_prompt += "\n     - 重要：当用户要求打开程序时，优先使用 open_program 命令"
        base_prompt += "\n     - 开启b站: /enable_website b站"
        base_prompt += "\n     - 关闭鸣潮: /disable_program 鸣潮"
        base_prompt += "\n<|im_end|>"
        
        return base_prompt
    
    # 对话历史限制
    MAX_HISTORY_LENGTH = 10  # 保留最近10轮对话
    
    # 合我意 TTS 配置
    ENABLE_TTS = os.getenv("ENABLE_TTS", "false").lower() == "true"
    HEWOYI_API_KEY = os.getenv("HEWOYI_API_KEY", "Flg6c0gtkhk1KInva0uzrcs2Gf")
    HEWOYI_VOICE = os.getenv("HEWOYI_VOICE", "zh-CN-XiaoyiNeural")  # 默认语音
    HEWOYI_SPEED = float(os.getenv("HEWOYI_SPEED", "1.0"))  # 默认语速1.0
    HEWOYI_TONE = int(os.getenv("HEWOYI_TONE", "5"))  # 默认音调5
    HEWOYI_FORMAT = os.getenv("HEWOYI_FORMAT", "mp3")  # 音频格式

    # 长期记忆配置
    ENABLE_LONG_TERM_MEMORY = os.getenv("ENABLE_LONG_TERM_MEMORY", "true").lower() == "true"
    MEMORY_DB_PATH = os.path.join(os.path.dirname(__file__), "memory_db", "memory")  # 在这里定义路径
    MEMORY_RETRIEVAL_TOP_K = int(os.getenv("MEMORY_RETRIEVAL_TOP_K", "3"))  # 检索最相关的K条记忆
    MEMORY_EMBEDDING_MODEL = os.getenv("MEMORY_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")  # 嵌入模型

    # 字幕配置
    ENABLE_SUBTITLES = os.getenv("ENABLE_SUBTITLES", "true").lower() == "true"

    # 字幕窗口显示设置
    SUBTITLE_FRAMELESS = os.getenv("SUBTITLE_FRAMELESS", "true").lower() == "true"         # 无边框窗口
    SUBTITLE_CLICK_THROUGH = os.getenv("SUBTITLE_CLICK_THROUGH", "true").lower() == "true" # 鼠标穿透
    SUBTITLE_TOPMOST = os.getenv("SUBTITLE_TOPMOST", "true").lower() == "true"             # 置于顶层
    SUBTITLE_TRANSPARENT = os.getenv("SUBTITLE_TRANSPARENT", "true").lower() == "true"     # 透明背景
    
    # 透明背景颜色（r,g,b） - 使用色键透明
    SUBTITLE_TRANSPARENT_COLOR = tuple(
        int(c) for c in os.getenv("SUBTITLE_TRANSPARENT_COLOR", "0,0,0").split(",")
    )

    # 字幕字体和窗口设置
    SUBTITLE_FONT_NAME = os.getenv("SUBTITLE_FONT_NAME", "SimHei")  # 字体名称
    SUBTITLE_FONT_SIZE = int(os.getenv("SUBTITLE_FONT_SIZE", "36"))  # 初始字体大小
    SUBTITLE_ANTIALIAS = os.getenv("SUBTITLE_ANTIALIAS", "false").lower() == "true"  # 字体抗锯齿
    SUBTITLE_COLOR = tuple(int(c) for c in os.getenv("SUBTITLE_COLOR", "255,255,255").split(","))  # 字体颜色
    SUBTITLE_OUTLINE_COLOR = tuple(int(c) for c in os.getenv("SUBTITLE_OUTLINE_COLOR", "0,0,0").split(","))  # 轮廓颜色
    SUBTITLE_OUTLINE_SIZE = int(os.getenv("SUBTITLE_OUTLINE_SIZE", "2"))  # 轮廓大小
    SUBTITLE_WIDTH = int(os.getenv("SUBTITLE_WIDTH", "800"))         # 窗口宽度
    SUBTITLE_HEIGHT = int(os.getenv("SUBTITLE_HEIGHT", "200"))       # 窗口高度
    SUBTITLE_FPS = int(os.getenv("SUBTITLE_FPS", "120"))             # 刷新帧率
    
    # 字幕效果设置
    SUBTITLE_TYPING_SPEED = float(os.getenv("SUBTITLE_TYPING_SPEED", "0.15"))  # 每个字的打字时间（秒）
    SUBTITLE_AUDIO_CHAR_TIME = float(os.getenv("SUBTITLE_AUDIO_CHAR_TIME", "0.2"))  # 估算语音每个字的时间
    SUBTITLE_EXTRA_DISPLAY_TIME = float(os.getenv("SUBTITLE_EXTRA_DISPLAY_TIME", "4.0"))  # 打完字后额外显示时间（秒）
    
    # 字幕调试设置
    SUBTITLE_DEBUG_VERBOSE = os.getenv("SUBTITLE_DEBUG_VERBOSE", "false").lower() == "true"
    SUBTITLE_LOG_EVERY_N_FRAMES = int(os.getenv("SUBTITLE_LOG_EVERY_N_FRAMES", "60"))
    SUBTITLE_WATCHDOG_TIMEOUT = float(os.getenv("SUBTITLE_WATCHDOG_TIMEOUT", "3.0"))  # 看门狗超时时间（秒）
    SUBTITLE_IDLE_FPS = int(os.getenv("SUBTITLE_IDLE_FPS", "30"))  # 空闲时帧率
    
# 在类定义完成后设置 CHARACTER_PROMPT
Config.CHARACTER_PROMPT = Config.build_character_prompt()