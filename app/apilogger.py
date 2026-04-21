"""Logging utilities for the IRI Facility API."""

import logging
import os
import sys
from pathlib import Path

LEVELS = {"FATAL": logging.FATAL,
          "ERROR": logging.ERROR,
          "WARNING": logging.WARNING,
          "INFO": logging.INFO,
          "DEBUG": logging.DEBUG}

DEFAULT_FORMAT = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S"
IRI_HANDLER_ATTR = "_iri_facility_api_handler"

_CONFIGURED = False


def _level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    return LEVELS.get(str(level or "INFO").upper(), logging.INFO)


def _log_file_path() -> Path | None:
    log_file = os.environ.get("IRI_LOG_FILE") or os.environ.get("LOG_FILE")
    return Path(log_file) if log_file else None


def configure_logging(level: str | int | None = None) -> None:
    """
    Configure root logging for the API.

    Logs always go to stdout. If IRI_LOG_FILE or LOG_FILE is set, logs also go
    to that file.
    """
    global _CONFIGURED

    log_level = _level(level or os.environ.get("LOG_LEVEL"))
    root = logging.getLogger()
    root.setLevel(log_level)

    if _CONFIGURED:
        for handler in root.handlers:
            if getattr(handler, IRI_HANDLER_ATTR, False):
                handler.setLevel(log_level)
        return

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

    for handler in root.handlers[:]:
        if getattr(handler, IRI_HANDLER_ATTR, False):
            root.removeHandler(handler)
            handler.close()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    setattr(stdout_handler, IRI_HANDLER_ATTR, True)
    root.addHandler(stdout_handler)

    log_file = _log_file_path()
    if log_file:
        if log_file.parent != Path("."):
            log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        setattr(file_handler, IRI_HANDLER_ATTR, True)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_stream_logger(name: str = __name__, level: str = "DEBUG") -> logging.Logger:
    """
    Return a logger using the shared API stdout and optional file logging setup.
    """
    configure_logging(level)

    logger = logging.getLogger(name)
    logger.setLevel(_level(level))
    logger.propagate = True

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    return logger
