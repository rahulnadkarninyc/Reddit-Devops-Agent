import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )
    root.addHandler(h)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
