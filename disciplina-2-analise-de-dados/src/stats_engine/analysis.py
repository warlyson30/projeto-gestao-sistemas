"""
Motor de analise estatistica.

Implementa os tres blocos exigidos na entrega, com rigor metodologico
explicito em cada decisao:

1. Estatistica descritiva  - tendencia central, dispersao e coeficiente de
   variacao, este ultimo como medida adimensional de instabilidade de processo.
2. Analise de distribuicao - assimetria, curtose e teste formal de normalidade,
   cujo resultado determina qual familia de testes sera aplicada adiante.
3. Correlacao e associacao - Pearson, Spearman, ponto-bisserial, Mann-Whitney e
   qui-quadrado, acompanhados de valor-p e tamanho de efeito.

A decisao de projeto mais relevante deste modulo e o encadeamento entre os
blocos 2 e 3: o teste de normalidade nao e executado como formalidade
decorativa, e sim como criterio que seleciona o metodo subsequente. Reportar
apenas o coeficiente de Pearson sobre variaveis comprovadamente nao normais
seria um erro metodologico, ainda que o numero produzido parecesse plausivel.

Igualmente deliberada e a exigencia de tamanho de efeito ao lado de todo
valor-p. Em amostras da ordem de milhares de registros, diferencas
irrelevantes para o negocio atingem significancia estatistica com facilidade;
sem a magnitude do efeito, a significancia isolada induz a decisao equivocada.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from config.settings import STATS
from src.logger import get_logger

logger = get_logger("stats_engine")


# ---------------------------------------------------------------------------
# Estruturas de resultado
# ---------------------------------------------------------------------------


@dataclass
class DescriptiveResult:
    """Sumario descritivo de uma variavel continua."""

    variavel: str
    n: int
    media: float
    mediana: float
    desvio_padrao: float
    variancia: float
    coeficiente_variacao: float
    minimo: float
    q1: float
    q3: float
    maximo: float
    amplitude_interquartil: float
    interpretacao_estabilidade: str


@dataclass
class DistributionResult:
    """Caracterizacao da forma da distribuicao de uma variavel."""

    variavel: str
    n: int
    assimetria: float
    curtose_excesso: float
    teste_normalidade: str
    estatistica: float
    p_valor: float
    normal: bool
    interpretacao_assimetria: str
    implicacao_metodologica: str


@dataclass
class CorrelationResult:
    """Resultado de um teste de associacao entre duas variaveis."""

    variavel_x: str
    variavel_y: str
    metodo: str
    coeficiente: float
    p_valor: float
    n: int
    significativo: bool
    forca: str
    interpretacao: str


@dataclass
class GroupComparisonResult:
    """Comparacao de uma variavel continua entre dois grupos."""

    variavel: str
    agrupador: str
    grupo_a: str
    grupo_b: str
    n_a: int
    n_b: int
    media_a: float
    media_b: float
    mediana_a: float
    mediana_b: float
    diferenca_medias: float
    teste: str
    estatistica: float
    p_valor: float
    significativo: bool
    cohen_d: float
    magnitude_efeito: str
    interpretacao: str


@dataclass
class CategoricalAssociationResult:
    """Associacao entre duas variaveis categoricas."""

    variavel_a: str
    variavel_b: str
    teste: str
    qui_quadrado: float
    graus_liberdade: int
    p_valor: float
    n: int
    cramers_v: float
    significativo: bool
    forca: str
    interpretacao: str


@dataclass
class StatisticalReport:
    """Consolidacao de toda a analise estatistica."""

    descritivas: list[DescriptiveResult] = field(default_factory=list)
    distribuicoes: list[DistributionResult] = field(default_factory=list)
    correlacoes: list[CorrelationResult] = field(default_factory=list)
    comparacoes: list[GroupComparisonResult] = field(default_factory=list)
    associacoes: list[CategoricalAssociationResult] = field(default_factory=list)
    matriz_correlacao: dict[str, Any] = field(default_factory=dict)
    alpha: float = STATS.alpha
    executado_em: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "executado_em": self.executado_em,
            "nivel_significancia": self.alpha,
            "descritivas": [asdict(d) for d in self.descritivas],
            "distribuicoes": [asdict(d) for d in self.distribuicoes],
            "correlacoes": [asdict(c) for c in self.correlacoes],
            "comparacoes_de_grupos": [asdict(c) for c in self.comparacoes],
            "associacoes_categoricas": [asdict(a) for a in self.associacoes],
            "matriz_correlacao": self.matriz_correlacao,
        }

    def salvar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Relatorio estatistico gravado em %s.", caminho.name)


# ---------------------------------------------------------------------------
# Utilitarios de interpretacao
# ---------------------------------------------------------------------------


def _classificar(valor: float, faixas: tuple[tuple[float, str], ...]) -> str:
    """Classifica um valor absoluto segundo faixas ordenadas crescentes."""
    rotulo = faixas[0][1]
    for limite, nome in faixas:
        if abs(valor) >= limite:
            rotulo = nome
    return rotulo


def _interpretar_cv(cv: float) -> str:
    """
    Interpreta o coeficiente de variacao como medida de estabilidade de processo.

    O coeficiente de variacao e adimensional, o que permite comparar a
    dispersao de variaveis medidas em unidades diferentes, algo que o desvio
    padrao isolado nao possibilita.
    """
    if cv < 15:
        return "processo estavel: baixa dispersao relativa"
    if cv < 30:
        return "dispersao moderada: variabilidade aceitavel"
    if cv < 60:
        return "processo instavel: alta dispersao relativa"
    return "processo altamente instavel: dispersao supera a metade da media"


def _interpretar_assimetria(skew: float) -> str:
    if abs(skew) < STATS.limite_assimetria_moderada:
        return "aproximadamente simetrica"
    direcao = "a direita (cauda de valores altos)" if skew > 0 else "a esquerda (cauda de valores baixos)"
    intensidade = (
        "acentuada" if abs(skew) >= STATS.limite_assimetria_alta else "moderada"
    )
    return f"assimetria {intensidade} {direcao}"


def _cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    """
    Calcula o d de Cohen com desvio padrao combinado.

    Expressa a diferenca entre grupos em unidades de desvio padrao, tornando-a
    comparavel entre variaveis e independente do tamanho da amostra, ao
    contrario do valor-p.
    """
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return float("nan")
    var_a, var_b = np.var(a, ddof=1), np.var(b, ddof=1)
    denominador = n_a + n_b - 2
    if denominador <= 0:
        return float("nan")
    dp_combinado = np.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / denominador)
    if dp_combinado == 0:
        return float("nan")
    return float((np.mean(a) - np.mean(b)) / dp_combinado)


def _cramers_v(qui_quadrado: float, n: int, linhas: int, colunas: int) -> float:
    """
    Calcula o V de Cramer, tamanho de efeito para tabelas de contingencia.

    O qui-quadrado cresce proporcionalmente ao tamanho da amostra e por isso nao
    mede a intensidade da associacao. O V de Cramer normaliza a estatistica para
    o intervalo de zero a um, tornando-a interpretavel.
    """
    k = min(linhas - 1, colunas - 1)
    if n <= 0 or k <= 0:
        return float("nan")
    return float(np.sqrt(qui_quadrado / (n * k)))


# ---------------------------------------------------------------------------
# Bloco 1: estatistica descritiva
# ---------------------------------------------------------------------------


def analisar_descritiva(df: pd.DataFrame, variaveis: list[str]) -> list[DescriptiveResult]:
    """Calcula o sumario descritivo das variaveis continuas informadas."""
    resultados: list[DescriptiveResult] = []

    for variavel in variaveis:
        if variavel not in df.columns:
            logger.warning("Variavel '%s' ausente da base; descritiva ignorada.", variavel)
            continue

        serie = pd.to_numeric(df[variavel], errors="coerce").dropna()
        if len(serie) < 2:
            logger.warning("Variavel '%s' com amostra insuficiente.", variavel)
            continue

        media = float(serie.mean())
        desvio = float(serie.std(ddof=1))
        cv = (desvio / media * 100) if media != 0 else float("nan")
        q1, q3 = float(serie.quantile(0.25)), float(serie.quantile(0.75))

        resultados.append(
            DescriptiveResult(
                variavel=variavel,
                n=int(len(serie)),
                media=round(media, 4),
                mediana=round(float(serie.median()), 4),
                desvio_padrao=round(desvio, 4),
                variancia=round(float(serie.var(ddof=1)), 4),
                coeficiente_variacao=round(cv, 2),
                minimo=round(float(serie.min()), 4),
                q1=round(q1, 4),
                q3=round(q3, 4),
                maximo=round(float(serie.max()), 4),
                amplitude_interquartil=round(q3 - q1, 4),
                interpretacao_estabilidade=_interpretar_cv(cv),
            )
        )

    logger.info("Estatistica descritiva concluida para %d variaveis.", len(resultados))
    return resultados


# ---------------------------------------------------------------------------
# Bloco 2: distribuicao e normalidade
# ---------------------------------------------------------------------------


def analisar_distribuicao(
    df: pd.DataFrame, variaveis: list[str]
) -> list[DistributionResult]:
    """
    Caracteriza a forma da distribuicao e testa formalmente a normalidade.

    A escolha do teste depende do tamanho da amostra. Shapiro-Wilk possui maior
    poder em amostras pequenas, porem em amostras grandes rejeita a hipotese
    nula diante de desvios triviais, perdendo utilidade pratica. Acima do limite
    configurado, emprega-se o teste de D'Agostino-Pearson, que combina
    assimetria e curtose e e mais estavel nesse regime.
    """
    resultados: list[DistributionResult] = []

    for variavel in variaveis:
        if variavel not in df.columns:
            continue

        serie = pd.to_numeric(df[variavel], errors="coerce").dropna()
        n = len(serie)
        if n < 8:
            logger.warning(
                "Variavel '%s' com n=%d insuficiente para teste de normalidade.",
                variavel,
                n,
            )
            continue

        amostra = serie.to_numpy()
        assimetria = float(scipy_stats.skew(amostra, bias=False))
        curtose = float(scipy_stats.kurtosis(amostra, fisher=True, bias=False))

        if n <= STATS.shapiro_max_n:
            nome_teste = "Shapiro-Wilk"
            estatistica, p_valor = scipy_stats.shapiro(amostra)
        else:
            nome_teste = "D'Agostino-Pearson"
            estatistica, p_valor = scipy_stats.normaltest(amostra)

        normal = bool(p_valor > STATS.alpha)
        implicacao = (
            "Normalidade nao rejeitada: testes parametricos (Pearson, t de "
            "Student) sao aplicaveis."
            if normal
            else (
                "Normalidade rejeitada: a analise adota testes nao parametricos "
                "(Spearman, Mann-Whitney) como resultado principal, pois nao "
                "dependem do pressuposto violado."
            )
        )

        resultados.append(
            DistributionResult(
                variavel=variavel,
                n=int(n),
                assimetria=round(assimetria, 4),
                curtose_excesso=round(curtose, 4),
                teste_normalidade=nome_teste,
                estatistica=round(float(estatistica), 6),
                p_valor=float(f"{p_valor:.3e}"),
                normal=normal,
                interpretacao_assimetria=_interpretar_assimetria(assimetria),
                implicacao_metodologica=implicacao,
            )
        )

    logger.info("Analise de distribuicao concluida para %d variaveis.", len(resultados))
    return resultados


# ---------------------------------------------------------------------------
# Bloco 3: correlacao e associacao
# ---------------------------------------------------------------------------


def _extrair(resultado: Any) -> tuple[float, float]:
    """
    Normaliza o retorno das funcoes do scipy entre versoes.

    Versoes recentes retornam objetos com atributos ``statistic`` e ``pvalue``;
    versoes anteriores retornam tuplas. O Colab pode executar qualquer uma das
    duas, e o codigo precisa operar em ambas sem alteracao.
    """
    if hasattr(resultado, "statistic") and hasattr(resultado, "pvalue"):
        return float(resultado.statistic), float(resultado.pvalue)
    return float(resultado[0]), float(resultado[1])


def analisar_correlacoes(
    df: pd.DataFrame,
    pares: list[tuple[str, str]],
    distribuicoes: list[DistributionResult] | None = None,
) -> list[CorrelationResult]:
    """
    Testa a associacao entre pares de variaveis continuas.

    Para cada par sao calculados Pearson e Spearman. Pearson mede associacao
    linear e pressupoe normalidade bivariada; Spearman opera sobre postos, nao
    exige normalidade e captura relacoes monotonicas nao lineares. Quando a
    normalidade e rejeitada para alguma das variaveis do par, Spearman e
    sinalizado como o resultado de referencia.
    """
    normalidade = (
        {d.variavel: d.normal for d in distribuicoes} if distribuicoes else {}
    )
    resultados: list[CorrelationResult] = []

    for x, y in pares:
        if x not in df.columns or y not in df.columns:
            logger.warning("Par (%s, %s) ignorado: variavel ausente.", x, y)
            continue

        base = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(base) < 10:
            logger.warning("Par (%s, %s) ignorado: amostra insuficiente.", x, y)
            continue

        vetor_x = base[x].to_numpy()
        vetor_y = base[y].to_numpy()
        n = len(base)

        ambos_normais = normalidade.get(x, False) and normalidade.get(y, False)

        for metodo, funcao in (
            ("Pearson", scipy_stats.pearsonr),
            ("Spearman", scipy_stats.spearmanr),
        ):
            coeficiente, p_valor = _extrair(funcao(vetor_x, vetor_y))
            significativo = bool(p_valor < STATS.alpha)
            forca = _classificar(coeficiente, STATS.faixas_correlacao)
            sentido = "positiva" if coeficiente > 0 else "negativa"

            if metodo == "Pearson":
                nota = (
                    "resultado de referencia (normalidade nao rejeitada)"
                    if ambos_normais
                    else "reportado para comparacao; pressuposto de normalidade violado"
                )
            else:
                nota = (
                    "reportado para comparacao"
                    if ambos_normais
                    else "resultado de referencia (nao exige normalidade)"
                )

            interpretacao = (
                f"Associacao {sentido} {forca} "
                f"({'estatisticamente significativa' if significativo else 'nao significativa'} "
                f"ao nivel de {STATS.alpha:.0%}). {nota.capitalize()}."
            )

            resultados.append(
                CorrelationResult(
                    variavel_x=x,
                    variavel_y=y,
                    metodo=metodo,
                    coeficiente=round(coeficiente, 4),
                    p_valor=float(f"{p_valor:.3e}"),
                    n=int(n),
                    significativo=significativo,
                    forca=forca,
                    interpretacao=interpretacao,
                )
            )

    logger.info("Analise de correlacao concluida: %d testes executados.", len(resultados))
    return resultados


def analisar_correlacao_binaria(
    df: pd.DataFrame, variavel_binaria: str, variaveis_continuas: list[str]
) -> list[CorrelationResult]:
    """
    Mede a associacao entre uma variavel binaria e variaveis continuas.

    Emprega a correlacao ponto-bisserial, que e matematicamente equivalente ao
    coeficiente de Pearson quando uma das variaveis e dicotomica. E o
    instrumento adequado para quantificar o quanto a evasao se associa a cada
    variavel comportamental.
    """
    resultados: list[CorrelationResult] = []

    if variavel_binaria not in df.columns:
        logger.warning("Variavel binaria '%s' ausente da base.", variavel_binaria)
        return resultados

    binaria = df[variavel_binaria].astype(int)

    for variavel in variaveis_continuas:
        if variavel not in df.columns:
            continue

        base = pd.DataFrame(
            {"b": binaria, "c": pd.to_numeric(df[variavel], errors="coerce")}
        ).dropna()
        if len(base) < 10 or base["b"].nunique() < 2:
            continue

        coeficiente, p_valor = _extrair(
            scipy_stats.pointbiserialr(base["b"].to_numpy(), base["c"].to_numpy())
        )
        significativo = bool(p_valor < STATS.alpha)
        forca = _classificar(coeficiente, STATS.faixas_correlacao)
        sentido = "positiva" if coeficiente > 0 else "negativa"

        resultados.append(
            CorrelationResult(
                variavel_x=variavel_binaria,
                variavel_y=variavel,
                metodo="Ponto-bisserial",
                coeficiente=round(coeficiente, 4),
                p_valor=float(f"{p_valor:.3e}"),
                n=int(len(base)),
                significativo=significativo,
                forca=forca,
                interpretacao=(
                    f"Associacao {sentido} {forca} entre '{variavel_binaria}' e "
                    f"'{variavel}' "
                    f"({'significativa' if significativo else 'nao significativa'} "
                    f"ao nivel de {STATS.alpha:.0%})."
                ),
            )
        )

    logger.info(
        "Correlacao ponto-bisserial concluida: %d variaveis avaliadas.", len(resultados)
    )
    return resultados


def comparar_grupos(
    df: pd.DataFrame,
    variavel: str,
    agrupador: str,
    distribuicoes: list[DistributionResult] | None = None,
) -> GroupComparisonResult | None:
    """
    Compara uma variavel continua entre os dois niveis de uma variavel binaria.

    O teste e selecionado conforme o resultado da analise de normalidade: t de
    Student sob normalidade, Mann-Whitney caso contrario. O tamanho de efeito e
    sempre reportado, pois com amostras grandes a significancia estatistica
    isolada nao distingue diferenca relevante de diferenca trivial.
    """
    if variavel not in df.columns or agrupador not in df.columns:
        logger.warning("Comparacao (%s por %s) ignorada: variavel ausente.", variavel, agrupador)
        return None

    base = pd.DataFrame(
        {
            "valor": pd.to_numeric(df[variavel], errors="coerce"),
            "grupo": df[agrupador].astype(bool),
        }
    ).dropna()

    grupo_a = base.loc[base["grupo"], "valor"].to_numpy()
    grupo_b = base.loc[~base["grupo"], "valor"].to_numpy()

    if len(grupo_a) < 3 or len(grupo_b) < 3:
        logger.warning("Comparacao (%s por %s) ignorada: grupo insuficiente.", variavel, agrupador)
        return None

    normal = next(
        (d.normal for d in (distribuicoes or []) if d.variavel == variavel), False
    )

    if normal:
        nome_teste = "t de Student (variancias desiguais, correcao de Welch)"
        estatistica, p_valor = _extrair(
            scipy_stats.ttest_ind(grupo_a, grupo_b, equal_var=False)
        )
    else:
        nome_teste = "Mann-Whitney U (nao parametrico)"
        estatistica, p_valor = _extrair(
            scipy_stats.mannwhitneyu(grupo_a, grupo_b, alternative="two-sided")
        )

    d = _cohen_d(grupo_a, grupo_b)
    magnitude = _classificar(d, STATS.faixas_cohen_d)
    significativo = bool(p_valor < STATS.alpha)
    diferenca = float(np.mean(grupo_a) - np.mean(grupo_b))

    interpretacao = (
        f"A diferenca media de {diferenca:+.2f} em '{variavel}' entre os grupos "
        f"de '{agrupador}' e "
        f"{'estatisticamente significativa' if significativo else 'nao significativa'} "
        f"(p={p_valor:.3e}), com tamanho de efeito {magnitude} (d={d:.2f})."
    )

    return GroupComparisonResult(
        variavel=variavel,
        agrupador=agrupador,
        grupo_a=f"{agrupador}=True",
        grupo_b=f"{agrupador}=False",
        n_a=int(len(grupo_a)),
        n_b=int(len(grupo_b)),
        media_a=round(float(np.mean(grupo_a)), 4),
        media_b=round(float(np.mean(grupo_b)), 4),
        mediana_a=round(float(np.median(grupo_a)), 4),
        mediana_b=round(float(np.median(grupo_b)), 4),
        diferenca_medias=round(diferenca, 4),
        teste=nome_teste,
        estatistica=round(float(estatistica), 4),
        p_valor=float(f"{p_valor:.3e}"),
        significativo=significativo,
        cohen_d=round(d, 4) if not np.isnan(d) else float("nan"),
        magnitude_efeito=magnitude,
        interpretacao=interpretacao,
    )


def analisar_associacao_categorica(
    df: pd.DataFrame, variavel_a: str, variavel_b: str
) -> CategoricalAssociationResult | None:
    """
    Testa a independencia entre duas variaveis categoricas.

    Aplica o teste qui-quadrado de independencia e acompanha o resultado do V de
    Cramer. A estatistica qui-quadrado cresce com o tamanho da amostra e por si
    so nao informa a intensidade da associacao; o V de Cramer a normaliza para o
    intervalo de zero a um.
    """
    if variavel_a not in df.columns or variavel_b not in df.columns:
        return None

    tabela = pd.crosstab(df[variavel_a], df[variavel_b])
    if tabela.shape[0] < 2 or tabela.shape[1] < 2:
        return None

    resultado = scipy_stats.chi2_contingency(tabela)
    qui_quadrado = float(resultado[0])
    p_valor = float(resultado[1])
    graus_liberdade = int(resultado[2])

    n = int(tabela.to_numpy().sum())
    v = _cramers_v(qui_quadrado, n, tabela.shape[0], tabela.shape[1])
    significativo = bool(p_valor < STATS.alpha)
    forca = _classificar(v, STATS.faixas_correlacao)

    return CategoricalAssociationResult(
        variavel_a=variavel_a,
        variavel_b=variavel_b,
        teste="Qui-quadrado de independencia",
        qui_quadrado=round(qui_quadrado, 4),
        graus_liberdade=graus_liberdade,
        p_valor=float(f"{p_valor:.3e}"),
        n=n,
        cramers_v=round(v, 4),
        significativo=significativo,
        forca=forca,
        interpretacao=(
            f"As variaveis '{variavel_a}' e '{variavel_b}' "
            f"{'nao sao independentes' if significativo else 'nao apresentam associacao detectavel'} "
            f"(p={p_valor:.3e}); intensidade {forca} (V de Cramer = {v:.3f})."
        ),
    )


def construir_matriz_correlacao(
    df: pd.DataFrame, variaveis: list[str], metodo: str = "spearman"
) -> dict[str, Any]:
    """
    Constroi a matriz de correlacao usada no mapa de calor.

    O metodo padrao e Spearman por nao exigir normalidade, pressuposto
    tipicamente violado pelas variaveis comportamentais desta base.
    """
    presentes = [v for v in variaveis if v in df.columns]
    base = df[presentes].apply(pd.to_numeric, errors="coerce")
    matriz = base.corr(method=metodo).round(4)

    return {
        "metodo": metodo,
        "variaveis": presentes,
        "matriz": {
            linha: {coluna: (None if pd.isna(valor) else float(valor))
                    for coluna, valor in dados.items()}
            for linha, dados in matriz.to_dict(orient="index").items()
        },
        "colinearidades": detectar_colinearidade(matriz),
    }


def detectar_colinearidade(
    matriz: pd.DataFrame, limite: float = 0.90
) -> list[dict[str, Any]]:
    """
    Identifica pares de variaveis com correlacao proxima da perfeita.

    A deteccao e automatizada, e nao deixada a inspecao visual do mapa de calor,
    porque a colinearidade tem consequencia metodologica concreta: duas
    variaveis com correlacao acima do limite carregam essencialmente a mesma
    informacao. Trata-las como evidencias independentes constitui dupla
    contagem, e utiliza-las simultaneamente em um modelo posterior torna os
    coeficientes instaveis.

    Args:
        matriz: matriz de correlacao quadrada.
        limite: valor absoluto a partir do qual o par e sinalizado.

    Returns:
        Lista de pares sinalizados com o respectivo diagnostico.
    """
    achados: list[dict[str, Any]] = []
    colunas = list(matriz.columns)

    for i, variavel_a in enumerate(colunas):
        for variavel_b in colunas[i + 1 :]:
            coeficiente = matriz.loc[variavel_a, variavel_b]
            if pd.isna(coeficiente) or abs(coeficiente) < limite:
                continue
            achados.append(
                {
                    "variavel_a": variavel_a,
                    "variavel_b": variavel_b,
                    "coeficiente": round(float(coeficiente), 4),
                    "diagnostico": (
                        f"Correlacao de magnitude {abs(coeficiente):.2f} entre "
                        f"'{variavel_a}' e '{variavel_b}' indica redundancia "
                        "informacional. As duas variaveis nao devem ser tratadas "
                        "como evidencias independentes no relatorio, nem "
                        "utilizadas em conjunto em modelagem posterior."
                    ),
                }
            )

    if achados:
        logger.warning(
            "Colinearidade detectada em %d par(es) de variaveis (limite=%.2f).",
            len(achados),
            limite,
        )
    return achados
