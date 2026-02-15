import logging
import os
from datetime import datetime

from config import LOG_LEVEL


def setup_logging():
    """Configura sistema de logging do CPES."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(
        log_dir, f"cpes_{datetime.now().strftime('%Y%m%d')}.log"
    )

    # Formato
    fmt = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Handler de arquivo
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # Handler de console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silenciar logs verbose de libs externas
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger("CPES")
    logger.info(f"Logging inicializado - Nivel: {LOG_LEVEL} - Arquivo: {log_file}")

    return logger
