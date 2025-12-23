import logging
import logging.config
import os
from pathlib import Path
from typing import Optional

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
DEFAULT_LOG_FILE = "logs/app.log"
DEFAULT_LOG_OUTPUT = "console"  # file | console
DEFAULT_ROTATION_WHEN = "midnight"
DEFAULT_ROTATION_INTERVAL = 1
DEFAULT_RETENTION = 14  # number of rotated files to keep

NOISY_LOGGERS = {
    "websockets": "WARNING",
    "websockets.client": "WARNING",
    "websockets.server": "WARNING",
    "python_multipart.multipart": "WARNING",
    "asyncio": "INFO",
    "uvicorn.access": "INFO",
    "uvicorn.error": "INFO",
    # TODO: add any other noisy loggers you see here when DEBUG enabled.
    # "urllib3": "WARNING",
}


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure application-wide logging.

    The configuration is idempotent so it can be invoked from scripts, tests,
    and the API without duplicating handlers. Log level and format can be
    overridden via the LOG_LEVEL environment variable.

    Console logging is the default (LOG_OUTPUT=console). To log to a file set
    LOG_OUTPUT=file. File location, rotation cadence, and retention are
    configurable via environment variables.
    """
    log_level = (level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    log_output = os.getenv("LOG_OUTPUT", DEFAULT_LOG_OUTPUT).lower()
    log_to_file = log_output == "file"

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stderr",
        }
    }
    root_handlers = ["console"]

    if log_to_file:
        log_file = Path(os.getenv("LOG_FILE", DEFAULT_LOG_FILE))
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "standard",
            "filename": os.getenv("LOG_FILE", DEFAULT_LOG_FILE),
            "when": os.getenv("LOG_ROTATION_WHEN", DEFAULT_ROTATION_WHEN),
            "interval": int(os.getenv("LOG_ROTATION_INTERVAL", DEFAULT_ROTATION_INTERVAL)),
            "backupCount": int(os.getenv("LOG_RETENTION", DEFAULT_RETENTION)),
            "utc": True,
            "encoding": "utf-8",
        }
        root_handlers = ["file"]

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": os.getenv("LOG_FORMAT", DEFAULT_FORMAT),
                    "datefmt": os.getenv("LOG_DATE_FORMAT", DEFAULT_DATE_FORMAT),
                }
            },
            "loggers": {name: {"level": lvl, "propagate": True} for name, lvl in NOISY_LOGGERS.items()},
            "handlers": handlers,
            "root": {
                "handlers": root_handlers,
                "level": log_level,
            },
        }
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
