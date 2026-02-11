"""Настройка логирования."""

import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Перенаправить записи stdlib logging в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Отправить запись лога в loguru.

        Parameters
        ----------
        record : logging.LogRecord
            Запись из стандартного логгера.
        """
        if record.levelname in logger._core.levels:
            level = logger.level(record.levelname).name
        else:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def setup_logging(level: str) -> None:
    """Настроить loguru и перехват stdlib logging.

    Parameters
    ----------
    level : str
        Уровень логирования (например, `INFO`).
    """

    logger.remove()
    logger.add(sys.stdout, level=level, enqueue=True, backtrace=False, diagnose=False)

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(level)
