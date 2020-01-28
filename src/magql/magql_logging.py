import logging
import sys
from logging import FileHandler

FORMATTER = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
LOG_FILE = "magql.log"


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


def get_file_handler():
    file_handler = FileHandler(filename=LOG_FILE)
    file_handler.setFormatter(FORMATTER)
    return file_handler


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())
    logger.propagate = False

    return logger


magql_logger = get_logger("magql")
