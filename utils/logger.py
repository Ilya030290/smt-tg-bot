import logging
from config import LOGGING_FORMAT, LOGGING_LEVEL

def setup_logger(name=__name__):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOGGING_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOGGING_LEVEL)
    return logger
