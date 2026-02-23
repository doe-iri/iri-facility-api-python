"""Logging utilities for the IRI Facility API."""
import logging

LEVELS = {"FATAL": logging.FATAL,
          "ERROR": logging.ERROR,
          "WARNING": logging.WARNING,
          "INFO": logging.INFO,
          "DEBUG": logging.DEBUG}


def get_stream_logger(name: str = __name__, level: str = "DEBUG") -> logging.Logger:
    """
    Return a configured Stream logger.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()

        formatter = logging.Formatter("%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s", datefmt="%a, %d %b %Y %H:%M:%S")

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(LEVELS.get(level, logging.DEBUG))
    logger.propagate = False

    return logger