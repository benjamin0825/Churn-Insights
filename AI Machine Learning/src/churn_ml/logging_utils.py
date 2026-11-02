"""Logging setup and a small timing helper."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(level: str | int = "INFO") -> None:
    logging.basicConfig(level=level, format=_FORMAT, datefmt="%H:%M:%S", force=True)
    for noisy in ("optuna", "mlflow", "urllib3", "alembic", "matplotlib", "shap", "numba"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def timed(logger: logging.Logger, message: str) -> Iterator[None]:
    start = time.perf_counter()
    logger.info("%s ...", message)
    yield
    logger.info("%s done in %.1fs", message, time.perf_counter() - start)
