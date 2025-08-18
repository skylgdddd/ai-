import logging
import os
from logging.handlers import TimedRotatingFileHandler

class Logger:
    _logger = None

    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            cls._logger = logging.getLogger("NeuroSama")
            cls._logger.setLevel(logging.DEBUG)
            
            # 获取项目根目录路径
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 在项目根目录下创建logs目录
            log_dir = os.path.join(project_root, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 日志文件路径
            log_path = os.path.join(log_dir, "neuro_sama.log")
            
            # 文件日志 - 每天轮换，保留7天
            file_handler = TimedRotatingFileHandler(
                log_path,
                when="midnight",
                interval=1,
                backupCount=7,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            cls._logger.addHandler(file_handler)
            
        return cls._logger

# 全局日志实例
logger = Logger.get_logger()

if __name__ == "__main__":
    # 测试日志功能
    logger.debug("Debug 测试消息")
    logger.info("Info 测试消息")
    logger.warning("Warning 测试消息")
    logger.error("Error 测试消息")
    logger.critical("Critical 测试消息")