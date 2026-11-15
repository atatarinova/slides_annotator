"""Настройка логирования."""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Настраивает корневой логгер приложения."""
    logging.basicConfig(
        level=level.upper(),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер."""
    return logging.getLogger(name)
