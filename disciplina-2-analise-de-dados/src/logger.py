"""
Infraestrutura de logging do projeto.

Fornece um logger unico, configurado uma unica vez por processo, com saida
simultanea para console (nivel INFO) e arquivo rotativo (nivel DEBUG).
O rastro em arquivo e o que permite auditar uma execucao do pipeline depois
que ela terminou, requisito basico para operacao em ambiente produtivo.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR

_LOGGER_NAME = "vertice_fit"
_CONFIGURED = False

_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
_FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def _build_file_handler(log_dir: Path) -> RotatingFileHandler:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pipeline_{datetime.now():%Y%m%d}.log"
    handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    return handler


def _build_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def get_logger(module: str | None = None) -> logging.Logger:
    """
    Retorna o logger do projeto, configurando-o na primeira chamada.

    Args:
        module: sufixo opcional para identificar o modulo chamador.

    Returns:
        Instancia de logging.Logger pronta para uso.
    """
    global _CONFIGURED

    root = logging.getLogger(_LOGGER_NAME)

    if not _CONFIGURED:
        root.setLevel(logging.DEBUG)
        root.handlers.clear()
        root.addHandler(_build_console_handler())
        try:
            root.addHandler(_build_file_handler(LOGS_DIR))
        except OSError:
            # Ambientes efemeros (Colab sem permissao de escrita) nao devem
            # derrubar o pipeline por indisponibilidade do log em arquivo.
            root.warning("Log em arquivo indisponivel; seguindo apenas com console.")
        root.propagate = False
        _CONFIGURED = True

    return root if module is None else root.getChild(module)


def log_section(logger: logging.Logger, titulo: str) -> None:
    """Emite um separador de secao para tornar o log legivel em execucoes longas."""
    logger.info("")
    logger.info("=" * 78)
    logger.info(titulo.upper())
    logger.info("=" * 78)
