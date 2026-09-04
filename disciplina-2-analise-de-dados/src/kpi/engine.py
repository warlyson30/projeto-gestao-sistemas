"""
Motor de calculo dos indicadores.

Percorre o catalogo declarado em ``definitions.py``, executa cada calculo de
forma isolada e consolida o resultado em um relatorio serializavel.

O isolamento por indicador e intencional: a falha no calculo de um KPI e
capturada, registrada e nao interrompe os demais. Em um painel gerencial, a
indisponibilidade de uma metrica e preferivel a indisponibilidade do painel
inteiro.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config.settings import SMART_OBJECTIVES
from src.kpi.definitions import CATALOGO_KPI, KPIDefinition, carteira_de_risco
from src.logger import get_logger

logger = get_logger("kpi.engine")


@dataclass
class KPIResult:
    """Resultado do calculo de um indicador."""

    codigo: str
    nome: str
    valor: float
    unidade: str
    formula: str
    direcao_desejada: str
    objetivo_smart: str
    objetivo_descricao: str
    objetivo_meta: str
    justificativa: str
    erro: str | None = None

    @property
    def valor_formatado(self) -> str:
        if self.erro is not None or self.valor is None or np.isnan(self.valor):
            return "indisponivel"
        if self.unidade == "%":
            return f"{self.valor:.2f}%"
        if self.unidade.startswith("R$"):
            sufixo = "/mes" if "/mes" in self.unidade else ""
            return f"R$ {self.valor:,.2f}{sufixo}"
        return f"{self.valor:,.2f} {self.unidade}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "valor": None if (self.valor is None or np.isnan(self.valor)) else round(float(self.valor), 4),
            "valor_formatado": self.valor_formatado,
            "unidade": self.unidade,
            "formula": self.formula,
            "direcao_desejada": self.direcao_desejada,
            "objetivo_smart": self.objetivo_smart,
            "objetivo_descricao": self.objetivo_descricao,
            "objetivo_meta": self.objetivo_meta,
            "justificativa": self.justificativa,
            "erro": self.erro,
        }


@dataclass
class KPIReport:
    """Consolidacao dos indicadores calculados para uma base."""

    resultados: list[KPIResult] = field(default_factory=list)
    segmentacoes: dict[str, Any] = field(default_factory=dict)
    executado_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def obter(self, codigo: str) -> KPIResult | None:
        return next((r for r in self.resultados if r.codigo == codigo), None)

    def valor(self, codigo: str) -> float:
        resultado = self.obter(codigo)
        return float("nan") if resultado is None else resultado.valor

    def to_dict(self) -> dict[str, Any]:
        return {
            "executado_em": self.executado_em,
            "objetivos_smart": {
                k: {
                    "descricao": v.descricao,
                    "meta_numerica": v.meta_numerica,
                    "prazo": v.prazo,
                }
                for k, v in SMART_OBJECTIVES.items()
            },
            "indicadores": [r.to_dict() for r in self.resultados],
            "segmentacoes": self.segmentacoes,
        }

    def salvar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Relatorio de KPIs gravado em %s.", caminho.name)

    def to_frame(self) -> pd.DataFrame:
        """Converte o relatorio em tabela, formato usado na documentacao."""
        return pd.DataFrame(
            [
                {
                    "Codigo": r.codigo,
                    "Indicador": r.nome,
                    "Valor": r.valor_formatado,
                    "Direcao": r.direcao_desejada,
                    "Objetivo SMART": r.objetivo_smart,
                }
                for r in self.resultados
            ]
        )

    def imprimir(self) -> None:
        """Emite o painel de indicadores no log."""
        logger.info("-" * 78)
        logger.info("PAINEL DE INDICADORES")
        logger.info("-" * 78)
        for r in self.resultados:
            marcador = "!" if r.erro else " "
            logger.info(
                "%s %-8s %-46s %18s",
                marcador,
                r.codigo,
                r.nome[:46],
                r.valor_formatado,
            )
        logger.info("-" * 78)


# ---------------------------------------------------------------------------
# Execucao
# ---------------------------------------------------------------------------


def _executar_indicador(definicao: KPIDefinition, df: pd.DataFrame) -> KPIResult:
    """Executa um indicador isolando eventual falha de calculo."""
    try:
        valor = definicao.avaliar(df)
        erro = None
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        valor = float("nan")
        erro = f"{exc.__class__.__name__}: {exc}"
        logger.error("Falha no calculo de %s: %s", definicao.codigo, erro)

    return KPIResult(
        codigo=definicao.codigo,
        nome=definicao.nome,
        valor=valor,
        unidade=definicao.unidade,
        formula=definicao.formula,
        direcao_desejada=definicao.direcao_desejada,
        objetivo_smart=definicao.objetivo_smart,
        objetivo_descricao=definicao.objetivo_descricao,
        objetivo_meta=definicao.objetivo_meta,
        justificativa=definicao.justificativa,
        erro=erro,
    )


def _segmentar_churn(df: pd.DataFrame, coluna: str) -> dict[str, Any]:
    """
    Calcula a taxa de evasao por categoria de uma dimensao.

    A segmentacao e o que transforma um indicador agregado em informacao
    acionavel: uma taxa global de evasao nao indica onde intervir, ao passo que
    a taxa por segmento aponta o publico especifico da acao.
    """
    if coluna not in df.columns:
        return {}

    agrupado = df.groupby(coluna, observed=True).agg(
        alunos=("id_aluno", "count"),
        evasoes=("evadiu", "sum"),
        frequencia_media=("frequencia_semanal", "mean"),
        ticket_medio=("valor_mensalidade", "mean"),
    )
    agrupado["taxa_evasao_pct"] = (agrupado["evasoes"] / agrupado["alunos"] * 100).round(2)
    agrupado["frequencia_media"] = agrupado["frequencia_media"].round(2)
    agrupado["ticket_medio"] = agrupado["ticket_medio"].round(2)
    agrupado["evasoes"] = agrupado["evasoes"].astype(int)

    return {
        str(indice): {k: (int(v) if isinstance(v, (int, np.integer)) else float(v))
                      for k, v in linha.items()}
        for indice, linha in agrupado.to_dict(orient="index").items()
    }


def calcular_kpis(df: pd.DataFrame) -> KPIReport:
    """
    Executa o catalogo completo de indicadores sobre a base analitica.

    Args:
        df: base analitica ja processada pelo ETL.

    Returns:
        Relatorio consolidado com valores, metadados e segmentacoes.
    """
    logger.info("Calculando %d indicadores do catalogo.", len(CATALOGO_KPI))

    resultados = [_executar_indicador(d, df) for d in CATALOGO_KPI]

    segmentacoes = {
        "por_plano": _segmentar_churn(df, "plano"),
        "por_segmento_engajamento": _segmentar_churn(df, "segmento_engajamento"),
        "por_faixa_etaria": _segmentar_churn(df, "faixa_etaria"),
        "por_unidade": _segmentar_churn(df, "unidade"),
        "por_modalidade": _segmentar_churn(df, "modalidade_principal"),
    }

    # Comparativo direto da hipotese central do projeto: adesao digital e evasao.
    if {"usa_app", "evadiu"}.issubset(df.columns):
        com_app = df.loc[df["usa_app"], "evadiu"].mean() * 100
        sem_app = df.loc[~df["usa_app"], "evadiu"].mean() * 100
        segmentacoes["hipotese_adesao_digital"] = {
            "churn_com_app_pct": round(float(com_app), 2),
            "churn_sem_app_pct": round(float(sem_app), 2),
            "diferenca_pp": round(float(sem_app - com_app), 2),
            "risco_relativo": (
                round(float(sem_app / com_app), 2) if com_app > 0 else None
            ),
        }

    # Dimensionamento da carteira de risco sobre a base ativa.
    ativos = df.loc[~df["evadiu"]]
    if not ativos.empty:
        mascara_risco = carteira_de_risco(ativos)
        segmentacoes["carteira_de_risco"] = {
            "alunos_ativos": int(len(ativos)),
            "alunos_em_risco": int(mascara_risco.sum()),
            "participacao_pct": round(float(mascara_risco.mean() * 100), 2),
            "mrr_em_risco": round(
                float(ativos.loc[mascara_risco, "valor_mensalidade"].sum()), 2
            ),
        }

    relatorio = KPIReport(resultados=resultados, segmentacoes=segmentacoes)
    falhas = sum(1 for r in resultados if r.erro)
    if falhas:
        logger.warning("%d indicadores falharam e foram marcados como indisponiveis.", falhas)
    else:
        logger.info("Todos os %d indicadores calculados com sucesso.", len(resultados))

    return relatorio
