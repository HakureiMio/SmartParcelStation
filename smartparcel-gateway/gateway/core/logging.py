from __future__ import annotations

import sys
from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level.upper())
