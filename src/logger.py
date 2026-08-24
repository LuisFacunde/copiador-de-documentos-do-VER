import logging
import sys
from pathlib import Path


def configurar_logger(caminho_log: Path, numero_lote: int) -> logging.Logger:
    nome_logger = f"lote_{numero_lote}"
    logger = logging.getLogger(nome_logger)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    caminho_log = Path(caminho_log)
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(caminho_log), encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
