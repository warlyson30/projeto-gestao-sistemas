"""
Camada de carga (L do ETL).

Persiste a base analitica em dois formatos com finalidades distintas:

- Parquet (camada interim): preserva tipos nativos, incluindo datetime,
  boolean e categoricos. E o formato consumido pelas etapas seguintes do
  proprio pipeline, pois dispensa reinferencia de tipo a cada leitura.
- CSV (camada processed): formato de interoperabilidade, destinado a inspecao
  manual, anexo da documentacao e consumo por ferramentas externas.

Manter os dois evita o erro comum de reprocessar tipos a partir de CSV entre
etapas internas, que reintroduz exatamente os problemas de inferencia que o
ETL acabou de resolver.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import INTERIM_FILE, PROCESSED_FILE, ensure_directories
from src.logger import get_logger

logger = get_logger("etl.load")


def carregar(
    df: pd.DataFrame,
    caminho_interim: Path = INTERIM_FILE,
    caminho_processed: Path = PROCESSED_FILE,
) -> dict[str, Path]:
    """
    Persiste a base analitica nos formatos intermediario e final.

    Returns:
        Dicionario com os caminhos efetivamente gravados.
    """
    ensure_directories()
    gravados: dict[str, Path] = {}

    try:
        df.to_parquet(caminho_interim, index=False)
        gravados["interim"] = caminho_interim
        logger.info("Camada interim gravada em %s (Parquet).", caminho_interim.name)
    except (ImportError, ValueError) as exc:
        # pyarrow ausente nao deve interromper o pipeline: o CSV abaixo garante
        # a continuidade, com o custo de reinferencia de tipos na releitura.
        logger.warning(
            "Gravacao em Parquet indisponivel (%s). Prosseguindo apenas com CSV.",
            exc.__class__.__name__,
        )

    df.to_csv(caminho_processed, index=False, encoding="utf-8")
    gravados["processed"] = caminho_processed
    logger.info(
        "Camada processed gravada em %s (%d registros, %d colunas).",
        caminho_processed.name,
        len(df),
        df.shape[1],
    )

    return gravados


def ler_base_analitica(
    caminho_interim: Path = INTERIM_FILE, caminho_processed: Path = PROCESSED_FILE
) -> pd.DataFrame:
    """
    Recupera a base analitica priorizando o formato que preserva tipos.

    Raises:
        FileNotFoundError: se nenhuma das camadas estiver disponivel.
    """
    if caminho_interim.exists():
        df = pd.read_parquet(caminho_interim)
        logger.debug("Base analitica lida da camada interim (%d registros).", len(df))
        return df

    if caminho_processed.exists():
        df = pd.read_csv(
            caminho_processed,
            parse_dates=["data_matricula", "data_cancelamento"],
            encoding="utf-8",
        )
        logger.warning(
            "Camada interim ausente; base lida do CSV com reinferencia de tipos."
        )
        return df

    raise FileNotFoundError(
        "Base analitica nao encontrada. Execute o pipeline de ETL antes de "
        "consumir os dados processados."
    )
