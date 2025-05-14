import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(name=__name__):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    console_handler = logging.StreamHandler()
    oneline_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    oneline_handler.emit = lambda record: (
        oneline_handler.stream.write('\r' + oneline_handler.format(record)),
        oneline_handler.stream.flush()
    ) if not record.exc_info else oneline_handler.handleError(record)
    oneline_handler.setFormatter(formatter)

    # 添加一个自定义过滤器
    def console_filter(record):
        return not hasattr(record, 'oneline') or not record.oneline
    
    def oneline_filter(record):
        return hasattr(record, 'oneline') and record.oneline

    console_handler.addFilter(console_filter)
    oneline_handler.addFilter(oneline_filter)

    logger.addHandler(console_handler)
    logger.addHandler(oneline_handler)
    
    return logger

logger = setup_logger("SubtitleGenerator")