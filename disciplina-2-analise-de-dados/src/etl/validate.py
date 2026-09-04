"""
Qualidade de dados: perfilagem, validacao de dominio e trilha de auditoria.

O componente central deste modulo e o ``QualityLedger``. Cada tratamento
aplicado durante a transformacao registra nele uma entrada contendo a regra
executada, a coluna afetada, o volume de registros impactados e a justificativa
tecnica da decisao.

A motivacao e direta: um pipeline de ETL que altera dados sem deixar rastro nao
e auditavel. Se um KPI apresentar valor inesperado tres etapas adiante, o
ledger permite identificar exatamente qual regra de limpeza o produziu, sem
necessidade de reexecutar o processo em modo de depuracao.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.logger import get_logger

logger = get_logger("etl.validate")


# ---------------------------------------------------------------------------
# Trilha de auditoria
# ---------------------------------------------------------------------------


@dataclass
class TreatmentRecord:
    """Registro unitario de um tratamento aplicado a base."""

    etapa: str
    regra: str
    coluna: str
    registros_afetados: int
    acao: str
    justificativa: str

    def resumo(self) -> str:
        return (
            f"[{self.etapa}] {self.regra} | coluna={self.coluna} | "
            f"afetados={self.registros_afetados} | acao={self.acao}"
        )


@dataclass
class QualityLedger:
    """
    Livro-razao de qualidade de dados.

    Acumula os tratamentos aplicados e as metricas de volume antes e depois da
    transformacao, produzindo ao final um relatorio serializavel.
    """

    registros_entrada: int = 0
    registros_saida: int = 0
    tratamentos: list[TreatmentRecord] = field(default_factory=list)
    perfil_entrada: dict[str, Any] = field(default_factory=dict)
    perfil_saida: dict[str, Any] = field(default_factory=dict)
    executado_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def registrar(
        self,
        etapa: str,
        regra: str,
        coluna: str,
        registros_afetados: int,
        acao: str,
        justificativa: str,
    ) -> None:
        """Adiciona um tratamento a trilha e emite o log correspondente."""
        record = TreatmentRecord(
            etapa=etapa,
            regra=regra,
            coluna=coluna,
            registros_afetados=int(registros_afetados),
            acao=acao,
            justificativa=justificativa,
        )
        self.tratamentos.append(record)
        if registros_afetados > 0:
            logger.info(record.resumo())
        else:
            logger.debug("%s (nenhum registro afetado)", record.resumo())

    @property
    def registros_descartados(self) -> int:
        return self.registros_entrada - self.registros_saida

    @property
    def taxa_perda(self) -> float:
        if self.registros_entrada == 0:
            return 0.0
        return self.registros_descartados / self.registros_entrada

    def to_dict(self) -> dict[str, Any]:
        return {
            "executado_em": self.executado_em,
            "registros_entrada": self.registros_entrada,
            "registros_saida": self.registros_saida,
            "registros_descartados": self.registros_descartados,
            "taxa_perda": round(self.taxa_perda, 4),
            "total_tratamentos": len(self.tratamentos),
            "tratamentos": [asdict(t) for t in self.tratamentos],
            "perfil_entrada": self.perfil_entrada,
            "perfil_saida": self.perfil_saida,
        }

    def salvar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Relatorio de qualidade gravado em %s.", caminho.name)

    def imprimir_resumo(self) -> None:
        """Emite no log um sumario legivel da execucao do ETL."""
        logger.info("-" * 78)
        logger.info("SUMARIO DE QUALIDADE DE DADOS")
        logger.info("-" * 78)
        logger.info("Registros na entrada .......... %d", self.registros_entrada)
        logger.info("Registros na saida ............ %d", self.registros_saida)
        logger.info(
            "Registros descartados ......... %d (%.2f%%)",
            self.registros_descartados,
            self.taxa_perda * 100,
        )
        logger.info("Tratamentos aplicados ......... %d", len(self.tratamentos))
        logger.info("-" * 78)


# ---------------------------------------------------------------------------
# Perfilagem
# ---------------------------------------------------------------------------


def _json_safe(valor: Any) -> Any:
    """Converte tipos numpy/pandas para tipos nativos serializaveis em JSON."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating,)):
        return float(round(float(valor), 4))
    if isinstance(valor, (np.bool_,)):
        return bool(valor)
    if isinstance(valor, (pd.Timestamp, datetime)):
        return valor.isoformat()
    return valor


def perfilar(df: pd.DataFrame, rotulo: str) -> dict[str, Any]:
    """
    Produz o perfil estatistico e de completude da base.

    Diferente de um ``describe()`` isolado, este perfil e comparavel entre
    entrada e saida do ETL, permitindo demonstrar objetivamente o efeito da
    limpeza sobre a base.
    """
    perfil: dict[str, Any] = {
        "rotulo": rotulo,
        "n_registros": int(len(df)),
        "n_colunas": int(df.shape[1]),
        "memoria_mb": round(df.memory_usage(deep=True).sum() / 1_048_576, 3),
        "colunas": {},
    }

    for coluna in df.columns:
        serie = df[coluna]
        n_nulos = int(serie.isna().sum())
        info: dict[str, Any] = {
            "dtype": str(serie.dtype),
            "nulos": n_nulos,
            "pct_nulos": round(n_nulos / len(df) * 100, 2) if len(df) else 0.0,
            "distintos": int(serie.nunique(dropna=True)),
        }

        if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
            validos = serie.dropna()
            if len(validos) > 0:
                info.update(
                    {
                        "minimo": _json_safe(validos.min()),
                        "maximo": _json_safe(validos.max()),
                        "media": _json_safe(validos.mean()),
                        "mediana": _json_safe(validos.median()),
                    }
                )
        perfil["colunas"][coluna] = info

    logger.debug(
        "Perfil '%s': %d registros, %d colunas.", rotulo, perfil["n_registros"], perfil["n_colunas"]
    )
    return perfil


# ---------------------------------------------------------------------------
# Validacao de dominio
# ---------------------------------------------------------------------------


def mascara_fora_dominio_numerico(
    serie: pd.Series, minimo: float | None = None, maximo: float | None = None
) -> pd.Series:
    """
    Retorna a mascara booleana dos valores fora do intervalo de dominio.

    Valores nulos nao sao considerados violacao de dominio: ausencia e um
    problema de completude, tratado separadamente por imputacao.
    """
    mascara = pd.Series(False, index=serie.index)
    if minimo is not None:
        mascara = mascara | (serie < minimo)
    if maximo is not None:
        mascara = mascara | (serie > maximo)
    return mascara & serie.notna()


def mascara_fora_dominio_categorico(
    serie: pd.Series, valores_validos: tuple[str, ...]
) -> pd.Series:
    """Retorna a mascara dos valores categoricos nao previstos no dominio."""
    return (~serie.isin(valores_validos)) & serie.notna()


def detectar_outliers_iqr(
    serie: pd.Series, multiplicador: float = 1.5
) -> tuple[pd.Series, dict[str, float]]:
    """
    Detecta outliers pelo criterio de Tukey (amplitude interquartil).

    O metodo IQR e preferido ao criterio de desvios-padrao (z-score) porque
    nao pressupoe normalidade e porque seus proprios limites nao sao
    influenciados pelos valores extremos que se pretende identificar.

    Returns:
        Tupla com a mascara booleana de outliers e os limites calculados.
    """
    validos = serie.dropna()
    if len(validos) < 4:
        return pd.Series(False, index=serie.index), {}

    q1 = float(validos.quantile(0.25))
    q3 = float(validos.quantile(0.75))
    iqr = q3 - q1
    limite_inferior = q1 - multiplicador * iqr
    limite_superior = q3 + multiplicador * iqr

    mascara = ((serie < limite_inferior) | (serie > limite_superior)) & serie.notna()

    limites = {
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "limite_inferior": round(limite_inferior, 4),
        "limite_superior": round(limite_superior, 4),
    }
    return mascara, limites
