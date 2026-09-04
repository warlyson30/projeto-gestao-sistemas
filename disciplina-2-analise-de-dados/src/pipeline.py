"""
Orquestrador do pipeline analitico.

Encadeia as quatro etapas do processo em uma unica unidade executavel e
reprodutivel: extracao e transformacao dos dados, calculo dos indicadores,
analise estatistica e geracao dos artefatos graficos.

A separacao entre orquestracao e implementacao e deliberada. Os modulos de ETL,
KPI, estatistica e visualizacao nao se conhecem entre si: nenhum importa o
outro. Toda a coordenacao ocorre exclusivamente aqui, de modo que substituir a
fonte de dados, acrescentar um indicador ou trocar a biblioteca grafica nao
exige alteracao nas demais camadas.

O pipeline distingue dois regimes de falha. Falhas estruturais, como ausencia
de coluna obrigatoria ou perda de registros acima do limite tolerado,
interrompem a execucao, pois qualquer resultado produzido adiante seria
invalido. Falhas localizadas, como um indicador ou um grafico especifico, sao
registradas e nao impedem a conclusao das demais etapas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import (
    FIGURES_DIR,
    KPI_REPORT_FILE,
    QUALITY_REPORT_FILE,
    STATS_REPORT_FILE,
    ensure_directories,
)
from src.etl.extract import SchemaError, extrair
from src.etl.load import carregar
from src.etl.transform import DataLossError, transformar
from src.etl.validate import QualityLedger, perfilar
from src.kpi.engine import KPIReport, calcular_kpis
from src.logger import get_logger, log_section
from src.stats_engine.analysis import StatisticalReport
from src.stats_engine.plan import VARIAVEIS_CONTINUAS, executar_analise
from src.viz import charts

logger = get_logger("pipeline")


class PipelineError(RuntimeError):
    """Falha estrutural que impede a continuidade da execucao."""


@dataclass
class PipelineResult:
    """Consolidacao dos artefatos produzidos por uma execucao."""

    base_analitica: pd.DataFrame
    ledger: QualityLedger
    kpis: KPIReport
    estatisticas: StatisticalReport
    figuras: dict[str, Path] = field(default_factory=dict)
    arquivos: dict[str, Path] = field(default_factory=dict)
    duracao_segundos: float = 0.0

    def resumo(self) -> dict[str, Any]:
        return {
            "registros_processados": int(len(self.base_analitica)),
            "registros_descartados": self.ledger.registros_descartados,
            "taxa_perda_pct": round(self.ledger.taxa_perda * 100, 2),
            "tratamentos_aplicados": len(self.ledger.tratamentos),
            "indicadores_calculados": len(self.kpis.resultados),
            "testes_estatisticos": (
                len(self.estatisticas.correlacoes)
                + len(self.estatisticas.comparacoes)
                + len(self.estatisticas.associacoes)
            ),
            "figuras_geradas": len(self.figuras),
            "duracao_segundos": round(self.duracao_segundos, 2),
        }


def executar_pipeline(
    forcar_regeracao: bool = False,
    gerar_figuras: bool = True,
    persistir: bool = True,
) -> PipelineResult:
    """
    Executa o pipeline analitico completo.

    Args:
        forcar_regeracao: regenera a base bruta antes da extracao.
        gerar_figuras: habilita a etapa de visualizacao.
        persistir: grava base processada e relatorios em disco.

    Returns:
        Resultado consolidado da execucao.

    Raises:
        PipelineError: em caso de falha estrutural no ETL.
    """
    inicio = time.perf_counter()
    ensure_directories()
    ledger = QualityLedger()
    arquivos: dict[str, Path] = {}

    # ------------------------------------------------------------------
    # Etapa 1: ETL
    # ------------------------------------------------------------------
    log_section(logger, "Etapa 1 de 4 | Extracao, transformacao e carga")
    try:
        bruta = extrair(forcar_regeracao=forcar_regeracao)
        ledger.perfil_entrada = perfilar(bruta, "base_bruta")

        analitica = transformar(bruta, ledger)
        ledger.perfil_saida = perfilar(analitica, "base_analitica")
        ledger.imprimir_resumo()

    except SchemaError as exc:
        raise PipelineError(
            f"Contrato de dados violado na origem: {exc}"
        ) from exc
    except DataLossError as exc:
        raise PipelineError(
            f"Perda de registros acima do tolerado: {exc}"
        ) from exc

    if persistir:
        arquivos.update(carregar(analitica))
        ledger.salvar(QUALITY_REPORT_FILE)
        arquivos["qualidade"] = QUALITY_REPORT_FILE

    # ------------------------------------------------------------------
    # Etapa 2: indicadores
    # ------------------------------------------------------------------
    log_section(logger, "Etapa 2 de 4 | Calculo dos indicadores")
    kpis = calcular_kpis(analitica)
    kpis.imprimir()
    if persistir:
        kpis.salvar(KPI_REPORT_FILE)
        arquivos["kpis"] = KPI_REPORT_FILE

    # ------------------------------------------------------------------
    # Etapa 3: analise estatistica
    # ------------------------------------------------------------------
    log_section(logger, "Etapa 3 de 4 | Analise estatistica")
    estatisticas = executar_analise(analitica)
    if persistir:
        estatisticas.salvar(STATS_REPORT_FILE)
        arquivos["estatisticas"] = STATS_REPORT_FILE

    # ------------------------------------------------------------------
    # Etapa 4: visualizacao
    # ------------------------------------------------------------------
    figuras: dict[str, Path] = {}
    if gerar_figuras:
        log_section(logger, "Etapa 4 de 4 | Geracao dos artefatos graficos")
        figuras = charts.gerar_todos(analitica, VARIAVEIS_CONTINUAS, FIGURES_DIR)
    else:
        logger.info("Etapa de visualizacao desabilitada por parametro.")

    duracao = time.perf_counter() - inicio

    resultado = PipelineResult(
        base_analitica=analitica,
        ledger=ledger,
        kpis=kpis,
        estatisticas=estatisticas,
        figuras=figuras,
        arquivos=arquivos,
        duracao_segundos=duracao,
    )

    log_section(logger, "Execucao concluida")
    for chave, valor in resultado.resumo().items():
        rotulo = chave.replace("_", " ").capitalize()
        logger.info("%s %s", rotulo.ljust(34, "."), valor)

    return resultado
