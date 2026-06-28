"""Central logging setup — file + console, shared by PoC and MVP backend."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = REPO_ROOT / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "app.log"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def get_log_level() -> int:
    name = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, name, logging.INFO)


def get_log_file() -> Path | None:
    raw = os.environ.get("LOG_FILE", str(DEFAULT_LOG_FILE)).strip()
    if not raw or raw.lower() in ("0", "false", "none", "off"):
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = get_log_level()
    log_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    root = logging.getLogger("leadfinder")
    root.setLevel(level)
    root.propagate = False

    if not root.handlers:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        root.addHandler(console)

        log_file = get_log_file()
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            root.info("Logging to %s (level=%s)", log_file, logging.getLevelName(level))

    # Quiet noisy third-party loggers unless DEBUG
    if level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    if not name.startswith("leadfinder"):
        name = f"leadfinder.{name}"
    return logging.getLogger(name)


def llm_debug_enabled() -> bool:
    return _env_bool("LOG_LLM_DEBUG", False)
