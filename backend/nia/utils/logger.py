import logging
import os
from pathlib import Path


class NiaLogger:
    _loggers = {}

    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    @classmethod
    def get_logger(cls, name="nia"):
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)

        config_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        log_level = level_map.get(config_level, logging.INFO)
        logger.setLevel(log_level)

        if not logger.handlers:
            formatter = logging.Formatter(cls.LOG_FORMAT)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "nia.log"

            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        logger.propagate = False
        cls._loggers[name] = logger
        return logger
