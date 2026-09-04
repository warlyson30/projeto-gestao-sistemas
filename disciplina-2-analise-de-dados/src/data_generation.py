"""
Gerador da base bruta da Academia Vertice Fit.

Este modulo simula a extracao de um sistema de gestao academico real. A base
produzida NAO e limpa: ela carrega defeitos deliberados equivalentes aos que
ocorrem em sistemas transacionais de producao (digitacao livre, integracoes
parciais, migracoes de legado). Isso e proposital, pois a etapa de ETL so tem
valor demonstravel se existir sujeira real a ser tratada.

Estrutura do processo gerador:

    1. Sorteia atributos independentes do aluno (plano, unidade, idade).
    2. Deriva o comportamento latente (frequencia, engajamento no app) a partir
       desses atributos, criando dependencias estatisticas reais.
    3. Calcula a probabilidade de evasao como funcao logistica do comportamento.
    4. Contamina a base com defeitos de qualidade parametrizados.

O passo 2 e o que garante que as correlacoes encontradas na Disciplina 2 sejam
verificaveis, e nao artefatos aleatorios.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import BUSINESS, RANDOM_SEED, SYNTHETIC, SyntheticDataConfig
from src.logger import get_logger

logger = get_logger("data_generation")


def _logistic(x: np.ndarray) -> np.ndarray:
    """Funcao logistica estavel numericamente."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _normal_truncada(
    rng: np.random.Generator,
    media: float,
    desvio: float,
    minimo: float,
    maximo: float,
    tamanho: int,
    max_iteracoes: int = 100,
) -> np.ndarray:
    """
    Amostra de uma normal truncada por rejeicao.

    Truncar e diferente de saturar (clip): a idade minima de matricula e uma
    regra de negocio que impede a existencia do registro, nao um teto que
    comprime observacoes reais contra a borda. Usar clip produziria um pico
    artificial no limite inferior, contaminando o histograma e a medida de
    assimetria calculados na etapa estatistica.
    """
    amostra = rng.normal(media, desvio, tamanho)
    for _ in range(max_iteracoes):
        invalidos = (amostra < minimo) | (amostra > maximo)
        n_invalidos = int(invalidos.sum())
        if n_invalidos == 0:
            return amostra
        amostra[invalidos] = rng.normal(media, desvio, n_invalidos)
    # Salvaguarda: apos o teto de iteracoes, satura o residuo remanescente.
    return np.clip(amostra, minimo, maximo)


def _gerar_nucleo(rng: np.random.Generator, cfg: SyntheticDataConfig) -> pd.DataFrame:
    """Gera os atributos limpos, antes de qualquer contaminacao."""
    n = cfg.n_alunos

    # --- Atributos independentes -------------------------------------------
    plano = rng.choice(
        BUSINESS.planos_validos, size=n, p=[0.55, 0.28, 0.17]
    )
    unidade = rng.choice(BUSINESS.unidades_validas, size=n, p=[0.45, 0.33, 0.22])
    idade = _normal_truncada(
        rng,
        media=32.0,
        desvio=11.0,
        minimo=float(BUSINESS.idade_min),
        maximo=float(BUSINESS.idade_max),
        tamanho=n,
    )
    idade = np.round(idade).astype(int)

    modalidade = rng.choice(
        BUSINESS.modalidades_validas, size=n, p=[0.40, 0.15, 0.20, 0.10, 0.15]
    )

    # Preco praticado: preco de tabela com desconto comercial residual
    preco_base = np.array([BUSINESS.preco_tabela[p] for p in plano])
    desconto = rng.choice([0.00, 0.05, 0.10], size=n, p=[0.72, 0.20, 0.08])
    valor_mensalidade = np.round(preco_base * (1 - desconto), 2)

    # Contratos com acompanhamento personalizado (personal trainer dedicado).
    # Representam parcela pequena da carteira, porem com ticket varias vezes
    # superior ao plano padrao. Sao valores legitimos, e nao erro de
    # lancamento: constituem os outliers monetarios que a analise deve
    # identificar e preservar, dado seu peso desproporcional na receita.
    idx_premium = rng.choice(n, size=int(n * 0.028), replace=False)
    adicional_personal = rng.uniform(180.0, 330.0, size=len(idx_premium))
    valor_mensalidade[idx_premium] = np.round(
        valor_mensalidade[idx_premium] + adicional_personal, 2
    )

    # --- Comportamento latente ---------------------------------------------
    # Planos de maior fidelidade tendem a frequencia levemente superior.
    bonus_plano = np.select(
        [plano == "Anual", plano == "Trimestral"], [0.55, 0.25], default=0.0
    )
    frequencia = rng.gamma(shape=4.0, scale=0.85, size=n) + bonus_plano
    frequencia = np.clip(frequencia, 0.0, BUSINESS.frequencia_max)

    # Adesao ao app: cresce com frequencia, decresce com idade.
    logito_app = -0.9 + 0.55 * frequencia - 0.035 * (idade - 32)
    usa_app = rng.random(n) < _logistic(logito_app)

    # Check-ins no app: so existem para quem usa o app; proporcionais a frequencia.
    checkins_app = np.where(
        usa_app,
        rng.poisson(np.clip(frequencia * 3.6, 0.1, None)),
        0,
    ).astype(int)

    # Hiperusuarios do aplicativo: parcela reduzida de alunos que registra
    # multiplas interacoes diarias (treino, dieta, agendamento). Produz a cauda
    # direita da distribuicao de engajamento digital, segmento de interesse
    # direto para a hipotese de retencao do TAP.
    candidatos = np.where(usa_app)[0]
    if len(candidatos) > 0:
        idx_hiper = rng.choice(
            candidatos, size=max(1, int(len(candidatos) * 0.035)), replace=False
        )
        checkins_app[idx_hiper] = (
            checkins_app[idx_hiper] + rng.integers(28, 62, size=len(idx_hiper))
        )

    # --- Datas --------------------------------------------------------------
    inicio = pd.Timestamp(BUSINESS.data_inicio_operacao)
    referencia = pd.Timestamp(BUSINESS.data_referencia)
    horizonte = (referencia - inicio).days

    dias_matricula = rng.integers(0, horizonte - 30, size=n)
    data_matricula = inicio + pd.to_timedelta(dias_matricula, unit="D")

    # --- Evasao -------------------------------------------------------------
    # Modelo logistico: frequencia e uso do app sao os fatores protetivos
    # dominantes; plano mensal e o fator de risco estrutural.
    risco_plano = np.select(
        [plano == "Mensal", plano == "Trimestral"], [0.85, 0.25], default=0.0
    )
    # Intercepto calibrado para reproduzir a faixa de evasao observada no setor
    # de academias no Brasil (aproximadamente 30% a 40% ao ano).
    logito_churn = (
        1.35
        - 0.62 * frequencia
        - 1.05 * usa_app.astype(float)
        + risco_plano
        + 0.012 * (idade - 32)
    )
    prob_churn = _logistic(logito_churn)
    evadiu = rng.random(n) < prob_churn

    # Tempo ate o cancelamento: concentrado nos primeiros meses (Weibull).
    dias_ate_evasao = np.round(rng.weibull(1.4, size=n) * 115 + 12).astype(int)
    dias_disponiveis = horizonte - dias_matricula
    # Quem nao teve tempo de vida suficiente na base nao pode ter evadido.
    evadiu = evadiu & (dias_ate_evasao < dias_disponiveis)

    data_cancelamento = pd.Series(pd.NaT, index=range(n), dtype="datetime64[ns]")
    idx_evadiu = np.where(evadiu)[0]
    data_cancelamento.iloc[idx_evadiu] = data_matricula[idx_evadiu] + pd.to_timedelta(
        dias_ate_evasao[idx_evadiu], unit="D"
    )

    df = pd.DataFrame(
        {
            "id_aluno": np.arange(1, n + 1),
            "data_matricula": data_matricula,
            "data_cancelamento": data_cancelamento.to_numpy(),
            "plano": plano,
            "valor_mensalidade": valor_mensalidade,
            "unidade": unidade,
            "modalidade_principal": modalidade,
            "idade": idade,
            "frequencia_semanal": np.round(frequencia, 2),
            "usa_app": usa_app,
            "checkins_app_mes": checkins_app,
        }
    )

    logger.debug("Nucleo sintetico gerado: %d registros limpos.", len(df))
    return df


def _contaminar(
    df: pd.DataFrame, rng: np.random.Generator, cfg: SyntheticDataConfig
) -> pd.DataFrame:
    """
    Injeta defeitos de qualidade equivalentes aos de um sistema real.

    Cada defeito injetado aqui possui tratamento correspondente no modulo de
    transformacao, garantindo que o ETL seja auditavel de ponta a ponta.
    """
    df = df.copy()
    n = len(df)

    def _amostra(taxa: float) -> np.ndarray:
        return rng.choice(n, size=int(n * taxa), replace=False)

    # 1. Valores ausentes por falha de integracao com a catraca / wearable
    df.loc[_amostra(cfg.taxa_nulos_frequencia), "frequencia_semanal"] = np.nan
    df.loc[_amostra(cfg.taxa_nulos_idade), "idade"] = np.nan
    df.loc[_amostra(cfg.taxa_nulos_modalidade), "modalidade_principal"] = None
    df.loc[_amostra(cfg.taxa_nulos_checkins), "checkins_app_mes"] = np.nan

    # 2. Inconsistencia de categoria por digitacao livre na recepcao
    idx_sujo = _amostra(cfg.taxa_categoria_suja)
    variacoes = {
        "Mensal": ["mensal", "MENSAL", " Mensal ", "mensal "],
        "Trimestral": ["trimestral", "TRIMESTRAL", " Trimestral"],
        "Anual": ["anual", "ANUAL", "Anual "],
    }
    planos_sujos = df.loc[idx_sujo, "plano"].map(
        lambda p: rng.choice(variacoes.get(p, [p]))
    )
    df["plano"] = df["plano"].astype(object)
    df.loc[idx_sujo, "plano"] = planos_sujos

    # 3. Valores fora de dominio por erro de lancamento manual
    idx_negativo = _amostra(cfg.taxa_valor_negativo)
    df.loc[idx_negativo, "valor_mensalidade"] = (
        df.loc[idx_negativo, "valor_mensalidade"] * -1
    )

    idx_idade = _amostra(cfg.taxa_idade_absurda)
    df.loc[idx_idade, "idade"] = rng.choice([0, 1, 150, 999], size=len(idx_idade))

    # 4. Datas em formato alternativo (migracao de sistema legado)
    df["data_matricula"] = df["data_matricula"].dt.strftime("%Y-%m-%d")
    df["data_cancelamento"] = pd.to_datetime(df["data_cancelamento"]).dt.strftime(
        "%Y-%m-%d"
    )

    idx_data_alt = _amostra(cfg.taxa_data_formato_alternativo)
    df.loc[idx_data_alt, "data_matricula"] = pd.to_datetime(
        df.loc[idx_data_alt, "data_matricula"]
    ).dt.strftime("%d/%m/%Y")

    # 5. Duplicatas por reenvio de lote na integracao
    idx_dup = _amostra(cfg.taxa_duplicatas)
    duplicatas = df.loc[idx_dup].copy()
    df = pd.concat([df, duplicatas], ignore_index=True)

    # 6. Espacos residuais em campos textuais
    df["unidade"] = df["unidade"].map(
        lambda u: f" {u} " if rng.random() < 0.10 else u
    )

    # Embaralha para que a ordem nao carregue informacao
    df = df.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)

    logger.debug("Contaminacao aplicada: base bruta com %d registros.", len(df))
    return df


def gerar_base_bruta(
    cfg: SyntheticDataConfig = SYNTHETIC, seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """
    Produz a base bruta completa, pronta para ser consumida pela etapa de extracao.

    Args:
        cfg: parametros de volume e taxas de contaminacao.
        seed: semente para reprodutibilidade integral da base.

    Returns:
        DataFrame bruto, com defeitos de qualidade presentes.
    """
    rng = np.random.default_rng(seed)
    nucleo = _gerar_nucleo(rng, cfg)
    bruto = _contaminar(nucleo, rng, cfg)
    logger.info(
        "Base bruta gerada: %d registros, %d colunas (semente=%d).",
        len(bruto),
        bruto.shape[1],
        seed,
    )
    return bruto
