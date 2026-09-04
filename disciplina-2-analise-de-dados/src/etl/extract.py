"""
Camada de extracao (E do ETL).

Responsabilidade unica: obter os dados da fonte e entrega-los ao pipeline sem
aplicar regra de negocio. Toda a leitura e feita com tipos permissivos
(``dtype=str`` onde ha risco de inferencia incorreta), porque a coercao de tipo
e responsabilidade da camada de transformacao, nao da leitura.

Esse limite e deliberado: se a extracao ja convertesse tipos, um valor invalido
na origem seria silenciosamente transformado em nulo pelo parser do pandas, e o
defeito de qualidade desapareceria do relatorio sem nunca ter sido contabilizado.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import RAW_FILE, SYNTHETIC, ensure_directories
from src.data_generation import gerar_base_bruta
from src.logger import get_logger

logger = get_logger("etl.extract")

# Contrato de entrada: colunas que a fonte obrigatoriamente deve fornecer.
SCHEMA_ESPERADO: tuple[str, ...] = (
    "id_aluno",
    "data_matricula",
    "data_cancelamento",
    "plano",
    "valor_mensalidade",
    "unidade",
    "modalidade_principal",
    "idade",
    "frequencia_semanal",
    "usa_app",
    "checkins_app_mes",
)


class SchemaError(ValueError):
    """Levantada quando a fonte nao cumpre o contrato de colunas esperado."""


def materializar_base_bruta(destino: Path = RAW_FILE, forcar: bool = False) -> Path:
    """
    Garante a existencia do arquivo bruto em disco.

    Em producao, esta funcao seria substituida pela consulta ao banco
    transacional do sistema de gestao. No escopo academico, a base e gerada
    de forma sintetica, porem determinística (semente fixa), o que preserva a
    reprodutibilidade exigida na entrega.

    Args:
        destino: caminho do CSV bruto.
        forcar: se True, regenera o arquivo mesmo que ja exista.

    Returns:
        Caminho do arquivo materializado.
    """
    ensure_directories()

    if destino.exists() and not forcar:
        logger.info("Base bruta ja existente em %s; extracao reutiliza o arquivo.", destino.name)
        return destino

    df = gerar_base_bruta(SYNTHETIC)
    df.to_csv(destino, index=False, encoding="utf-8")
    logger.info("Base bruta materializada em %s (%d registros).", destino.name, len(df))
    return destino


def validar_schema(df: pd.DataFrame) -> None:
    """
    Verifica o contrato de colunas antes de qualquer processamento.

    Falhar aqui e preferivel a falhar no meio da transformacao: o erro aponta
    diretamente para a origem, e nao para um sintoma tres etapas adiante.

    Raises:
        SchemaError: se houver coluna obrigatoria ausente.
    """
    ausentes = [c for c in SCHEMA_ESPERADO if c not in df.columns]
    if ausentes:
        raise SchemaError(
            f"Colunas obrigatorias ausentes na fonte: {ausentes}. "
            f"Colunas recebidas: {list(df.columns)}"
        )

    extras = [c for c in df.columns if c not in SCHEMA_ESPERADO]
    if extras:
        logger.warning("Colunas nao previstas no contrato serao ignoradas: %s", extras)

    logger.debug("Contrato de schema validado: %d colunas conformes.", len(SCHEMA_ESPERADO))


def extrair(origem: Path = RAW_FILE, forcar_regeracao: bool = False) -> pd.DataFrame:
    """
    Executa a extracao completa e devolve o DataFrame bruto.

    Args:
        origem: caminho do arquivo de origem.
        forcar_regeracao: repassa a flag de regeracao da base sintetica.

    Returns:
        DataFrame bruto, com tipos ainda nao normalizados.
    """
    caminho = materializar_base_bruta(origem, forcar=forcar_regeracao)

    # Leitura permissiva: campos sujeitos a sujeira sao lidos como texto para
    # que a transformacao possa contabilizar e tratar cada defeito.
    df = pd.read_csv(
        caminho,
        dtype={
            "data_matricula": "string",
            "data_cancelamento": "string",
            "plano": "string",
            "unidade": "string",
            "modalidade_principal": "string",
        },
        encoding="utf-8",
    )

    validar_schema(df)
    logger.info(
        "Extracao concluida: %d registros e %d colunas carregados de %s.",
        len(df),
        df.shape[1],
        caminho.name,
    )
    return df
