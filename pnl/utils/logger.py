import logging
import sys
from pnl.config import LOG_FILE

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File (rotating-friendly, append)
    try:
        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass  # If log file isn't writable, console is enough

    return logger
