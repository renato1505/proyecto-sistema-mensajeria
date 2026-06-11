import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR


def configurar_logging(app=None):
    logs_dir = Path(LOGS_DIR)
    if not logs_dir.is_absolute():
        logs_dir = Path(__file__).resolve().parent.parent / logs_dir

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "sistema_mensajeria.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == str(log_path)
        for handler in root_logger.handlers
    ):
        root_logger.addHandler(file_handler)

    if app:
        app.logger.setLevel(logging.INFO)
        app.logger.info("Portal Operativo iniciado")

    return log_path
