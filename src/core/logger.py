"""Loguru-based structured logger for the Multi-Agent Trading System.

Usage:
    from src.core.logger import get_logger
    log = get_logger("htf_bias_agent")
    log.info("HTF Bias detected: {bias}", bias="BULLISH")
"""

import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "trading_system.log"


def get_logger(name: str):
    """Return a configured loguru logger bound with the agent/module name."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>[{extra[agent]}]</cyan> | "
            "{message}"
        ),
    )
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(LOG_FILE),
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | [{extra[agent]}] | {message}",
        enqueue=True,
    )
    return logger.bind(agent=name)
