"""
Ponto de entrada do projeto Vertice Fit Analytics.

Executa o pipeline analitico completo a partir da linha de comando.

Uso:
    python main.py                      Execucao padrao
    python main.py --regenerar          Regenera a base bruta antes de executar
    python main.py --sem-figuras        Suprime a etapa de visualizacao
    python main.py --sem-persistencia   Executa em memoria, sem gravar artefatos

O codigo de saida segue a convencao de processos: zero em caso de sucesso e um
em caso de falha estrutural. Isso permite encadear a execucao em agendadores ou
esteiras de integracao continua sem inspecao do texto de log.
"""

from __future__ import annotations

import argparse
import sys

from src.logger import get_logger
from src.pipeline import PipelineError, executar_pipeline

logger = get_logger("main")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vertice-fit-analytics",
        description=(
            "Pipeline analitico da Academia Vertice Fit: ETL, indicadores, "
            "analise estatistica e visualizacao."
        ),
    )
    parser.add_argument(
        "--regenerar",
        action="store_true",
        help="regenera a base bruta antes da extracao",
    )
    parser.add_argument(
        "--sem-figuras",
        action="store_true",
        help="suprime a etapa de geracao de graficos",
    )
    parser.add_argument(
        "--sem-persistencia",
        action="store_true",
        help="executa em memoria, sem gravar arquivos de saida",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = construir_parser().parse_args(argv)

    try:
        resultado = executar_pipeline(
            forcar_regeracao=argumentos.regenerar,
            gerar_figuras=not argumentos.sem_figuras,
            persistir=not argumentos.sem_persistencia,
        )
    except PipelineError as exc:
        logger.critical("Pipeline interrompido: %s", exc)
        return 1
    except KeyboardInterrupt:
        logger.warning("Execucao interrompida pelo usuario.")
        return 130

    if resultado.arquivos:
        logger.info("")
        logger.info("Artefatos gravados:")
        for rotulo, caminho in resultado.arquivos.items():
            logger.info("  %-14s %s", rotulo, caminho)

    return 0


if __name__ == "__main__":
    sys.exit(main())
