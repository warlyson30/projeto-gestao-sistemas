"""
Plano de analise estatistica.

Declara explicitamente quais hipoteses serao testadas antes de qualquer
execucao. Essa ordem importa: fixar o plano previamente evita a pratica de
percorrer todas as combinacoes possiveis de variaveis e reportar apenas as que
resultaram significativas, procedimento que inflaciona artificialmente a taxa
de falsos positivos.

As hipoteses declaradas derivam diretamente dos objetivos do TAP:

    H1  A frequencia semanal associa-se negativamente a evasao.       (OE-01)
    H2  A adesao ao aplicativo associa-se negativamente a evasao.     (OE-03)
    H3  Frequencia e engajamento digital sao positivamente associados. (OE-03)
    H4  O tipo de plano associa-se a evasao.                          (OE-01)
    H5  A permanencia difere entre aderentes e nao aderentes ao app.  (OE-03)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.logger import get_logger
from src.stats_engine.analysis import (
    StatisticalReport,
    analisar_associacao_categorica,
    analisar_correlacao_binaria,
    analisar_correlacoes,
    analisar_descritiva,
    analisar_distribuicao,
    comparar_grupos,
    construir_matriz_correlacao,
)

logger = get_logger("stats_engine.plan")


@dataclass(frozen=True)
class Hypothesis:
    """Hipotese declarada antes da execucao da analise."""

    codigo: str
    enunciado: str
    objetivo_smart: str
    metodo: str


HIPOTESES: tuple[Hypothesis, ...] = (
    Hypothesis(
        codigo="H1",
        enunciado=(
            "A frequencia semanal de comparecimento associa-se negativamente a "
            "ocorrencia de evasao."
        ),
        objetivo_smart="OE-01",
        metodo="Correlacao ponto-bisserial e comparacao de grupos",
    ),
    Hypothesis(
        codigo="H2",
        enunciado=(
            "A adesao ao aplicativo associa-se negativamente a ocorrencia de "
            "evasao."
        ),
        objetivo_smart="OE-03",
        metodo="Qui-quadrado de independencia com V de Cramer",
    ),
    Hypothesis(
        codigo="H3",
        enunciado=(
            "Frequencia presencial e volume de interacoes no aplicativo sao "
            "positivamente associados."
        ),
        objetivo_smart="OE-03",
        metodo="Correlacao de Pearson e de Spearman",
    ),
    Hypothesis(
        codigo="H4",
        enunciado="O tipo de plano contratado associa-se a ocorrencia de evasao.",
        objetivo_smart="OE-01",
        metodo="Qui-quadrado de independencia com V de Cramer",
    ),
    Hypothesis(
        codigo="H5",
        enunciado=(
            "O tempo de permanencia difere entre alunos aderentes e nao "
            "aderentes ao aplicativo."
        ),
        objetivo_smart="OE-03",
        metodo="Mann-Whitney U com tamanho de efeito d de Cohen",
    ),
)


# Variaveis continuas centrais da analise
VARIAVEIS_CONTINUAS: list[str] = [
    "frequencia_semanal",
    "checkins_app_mes",
    "valor_mensalidade",
    "idade",
    "dias_vinculo",
    "receita_acumulada",
]

# Pares submetidos a teste de correlacao continua
PARES_CORRELACAO: list[tuple[str, str]] = [
    ("frequencia_semanal", "checkins_app_mes"),
    ("frequencia_semanal", "dias_vinculo"),
    ("checkins_app_mes", "dias_vinculo"),
    ("idade", "frequencia_semanal"),
    ("valor_mensalidade", "dias_vinculo"),
]

# Variaveis continuas confrontadas com o desfecho binario de evasao
CONTINUAS_VERSUS_EVASAO: list[str] = [
    "frequencia_semanal",
    "checkins_app_mes",
    "idade",
    "valor_mensalidade",
]


def executar_analise(df: pd.DataFrame) -> StatisticalReport:
    """
    Executa o plano completo de analise estatistica.

    Args:
        df: base analitica processada pelo ETL.

    Returns:
        Relatorio estatistico consolidado.
    """
    logger.info("Executando plano de analise com %d hipoteses declaradas.", len(HIPOTESES))

    # Bloco 1: descritiva
    descritivas = analisar_descritiva(df, VARIAVEIS_CONTINUAS)

    # Bloco 2: distribuicao e normalidade (determina o metodo do bloco 3)
    distribuicoes = analisar_distribuicao(df, VARIAVEIS_CONTINUAS)

    # Bloco 3: correlacoes entre continuas
    correlacoes = analisar_correlacoes(df, PARES_CORRELACAO, distribuicoes)

    # Bloco 3: associacao das continuas com o desfecho binario
    correlacoes += analisar_correlacao_binaria(df, "evadiu", CONTINUAS_VERSUS_EVASAO)

    # Bloco 3: comparacoes de grupo
    comparacoes = []
    for variavel, agrupador in (
        ("frequencia_semanal", "evadiu"),
        ("checkins_app_mes", "evadiu"),
        ("dias_vinculo", "usa_app"),
        ("frequencia_semanal", "usa_app"),
        ("receita_acumulada", "usa_app"),
    ):
        resultado = comparar_grupos(df, variavel, agrupador, distribuicoes)
        if resultado is not None:
            comparacoes.append(resultado)

    # Bloco 3: associacoes categoricas
    associacoes = []
    for variavel_a, variavel_b in (
        ("usa_app", "evadiu"),
        ("plano", "evadiu"),
        ("segmento_engajamento", "evadiu"),
        ("faixa_etaria", "evadiu"),
        ("unidade", "evadiu"),
    ):
        resultado = analisar_associacao_categorica(df, variavel_a, variavel_b)
        if resultado is not None:
            associacoes.append(resultado)

    matriz = construir_matriz_correlacao(df, VARIAVEIS_CONTINUAS, metodo="spearman")

    relatorio = StatisticalReport(
        descritivas=descritivas,
        distribuicoes=distribuicoes,
        correlacoes=correlacoes,
        comparacoes=comparacoes,
        associacoes=associacoes,
        matriz_correlacao=matriz,
    )

    logger.info(
        "Analise estatistica concluida: %d descritivas, %d testes de distribuicao, "
        "%d correlacoes, %d comparacoes, %d associacoes.",
        len(descritivas),
        len(distribuicoes),
        len(correlacoes),
        len(comparacoes),
        len(associacoes),
    )
    return relatorio
