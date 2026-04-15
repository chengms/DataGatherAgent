"""Lightweight logging helpers used across the app."""

from __future__ import annotations

import functools
import logging
import sys
import time
from typing import Any, Callable, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class LoggerMixin:
    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_execution(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        logger = get_logger(func.__module__)
        started = time.perf_counter()
        logger.info("starting %s", func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception:
            logger.exception("failed %s", func.__name__)
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("finished %s in %.1fms", func.__name__, elapsed_ms)
        return result

    return wrapper  # type: ignore[return-value]
