"""
Camada de visualizacao.

Produz o conjunto de artefatos graficos da analise. Das dez opcoes previstas no
guia da disciplina, oito foram selecionadas e duas descartadas, com criterio
declarado em ``JUSTIFICATIVA_SELECAO``.

A selecao e deliberada e nao exaustiva. Um painel que reproduz todos os tipos
de grafico disponiveis demonstra dominio da biblioteca, nao dominio do
problema. Cada grafico aqui responde a uma pergunta especifica derivada das
hipoteses do plano de analise; os dois tipos descartados nao respondiam a
nenhuma.

O backend Agg e fixado explicitamente para permitir execucao em ambiente sem
interface grafica, condicao de qualquer pipeline automatizado.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from config.settings import BUSINESS, FIGURES_DIR, VIZ
from src.logger import get_logger

logger = get_logger("viz.charts")


JUSTIFICATIVA_SELECAO: dict[str, str] = {
    "barras": (
        "Comparacao da taxa de evasao entre segmentos de engajamento. E o "
        "grafico que traduz a hipotese central em ordem de grandeza imediata "
        "para a gestao."
    ),
    "linhas": (
        "Evolucao da evasao por coorte mensal de matricula. Distingue tendencia "
        "estrutural de variacao pontual, o que a taxa agregada nao permite."
    ),
    "dispersao": (
        "Relacao entre frequencia presencial e engajamento digital. Materializa "
        "visualmente o coeficiente de correlacao da hipotese H3."
    ),
    "histograma": (
        "Distribuicao da frequencia semanal. Sustenta visualmente o resultado do "
        "teste de normalidade que determinou a escolha dos metodos nao "
        "parametricos."
    ),
    "boxplot": (
        "Comparacao da distribuicao de frequencia entre evadidos e retidos. "
        "Exibe simultaneamente a separacao entre grupos e a presenca de valores "
        "extremos."
    ),
    "heatmap": (
        "Matriz de correlacao de Spearman. Permite leitura simultanea de todas "
        "as associacoes entre variaveis continuas, revelando redundancias."
    ),
    "pareto": (
        "Concentracao da receita acumulada por decil de aluno. Dimensiona a "
        "exposicao do faturamento a um numero reduzido de contratos."
    ),
    "violino": (
        "Distribuicao do tempo de vinculo por adesao ao aplicativo. Revela a "
        "forma completa da distribuicao, incluindo bimodalidade que o boxplot "
        "ocultaria."
    ),
    "descartado_pizza": (
        "Descartado. A composicao por status possui apenas duas categorias, "
        "informacao integralmente contida no indicador KPI-01. O grafico "
        "ocuparia espaco sem acrescentar leitura."
    ),
    "descartado_cascata": (
        "Descartado. Exige decomposicao sequencial de entradas e saidas "
        "financeiras mes a mes, informacao nao disponivel na base atual. "
        "Construi-lo demandaria estimativas nao verificaveis."
    ),
}


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------


def aplicar_tema() -> None:
    """
    Fixa o padrao visual unico do projeto.

    Centralizar o tema evita que cada grafico carregue configuracao propria,
    situacao que produz relatorios visualmente inconsistentes e dificulta a
    manutencao.
    """
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": VIZ.dpi,
            "savefig.dpi": VIZ.dpi,
            "savefig.bbox": "tight",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": VIZ.cor_grade,
            "axes.labelcolor": VIZ.cor_primaria,
            "axes.titlecolor": VIZ.cor_primaria,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "axes.grid": True,
            "grid.color": VIZ.cor_grade,
            "grid.linewidth": 0.8,
            "xtick.color": VIZ.cor_primaria,
            "ytick.color": VIZ.cor_primaria,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.frameon": False,
            "font.size": 10,
        }
    )


def _salvar(fig: plt.Figure, nome: str, destino: Path) -> Path:
    """Persiste a figura e libera a memoria associada."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{nome}.{VIZ.formato_arquivo}"
    fig.savefig(caminho)
    plt.close(fig)
    logger.info("Figura gravada: %s", caminho.name)
    return caminho


def _rotular_barras(ax: plt.Axes, valores: list[float], sufixo: str = "%") -> None:
    """Anota o valor sobre cada barra, dispensando a leitura pelo eixo."""
    for barra, valor in zip(ax.patches, valores):
        ax.annotate(
            f"{valor:.1f}{sufixo}",
            (barra.get_x() + barra.get_width() / 2, barra.get_height()),
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=VIZ.cor_primaria,
            xytext=(0, 3),
            textcoords="offset points",
        )


# ---------------------------------------------------------------------------
# Graficos
# ---------------------------------------------------------------------------


def grafico_barras_churn_por_segmento(df: pd.DataFrame, destino: Path) -> Path:
    """Taxa de evasao por segmento de engajamento, ordenada por severidade."""
    ordem = ["Alto", "Medio-Presencial", "Medio-Digital", "Baixo"]
    agrupado = (
        df.groupby("segmento_engajamento", observed=True)["evadiu"]
        .agg(["mean", "count"])
        .reindex([s for s in ordem if s in df["segmento_engajamento"].unique()])
        .dropna()
    )
    agrupado["taxa"] = agrupado["mean"] * 100

    cores = [
        VIZ.cor_sucesso if t < 20 else VIZ.cor_atencao if t < 40 else VIZ.cor_alerta
        for t in agrupado["taxa"]
    ]

    fig, ax = plt.subplots(figsize=VIZ.figsize_padrao)
    ax.bar(agrupado.index, agrupado["taxa"], color=cores, width=0.62)
    _rotular_barras(ax, agrupado["taxa"].tolist())

    media_geral = df["evadiu"].mean() * 100
    ax.axhline(
        media_geral,
        color=VIZ.cor_primaria,
        linestyle="--",
        linewidth=1.3,
        label=f"Media da carteira: {media_geral:.1f}%",
    )

    ax.set_title("Taxa de Evasao por Segmento de Engajamento")
    ax.set_xlabel("Segmento de engajamento")
    ax.set_ylabel("Taxa de evasao (%)")
    ax.set_ylim(0, max(agrupado["taxa"]) * 1.20)
    ax.legend(loc="upper left")

    rotulos = [
        f"{idx}\n(n={int(linha['count'])})" for idx, linha in agrupado.iterrows()
    ]
    ax.set_xticks(range(len(agrupado)))
    ax.set_xticklabels(rotulos)

    return _salvar(fig, "01_barras_churn_por_segmento", destino)


def calcular_coorte_janela_fixa(
    df: pd.DataFrame, janela_dias: int = 90, minimo_alunos: int = 15
) -> pd.DataFrame:
    """
    Calcula a taxa de evasao por coorte dentro de uma janela fixa de observacao.

    Esta funcao corrige um vies severo e frequente na analise de coortes: a
    censura a direita. Comparar a evasao acumulada de uma coorte matriculada ha
    dezoito meses com a de outra matriculada ha um mes produz queda aparente da
    evasao nas coortes recentes, quando na verdade elas apenas ainda nao
    tiveram tempo de evadir. A leitura ingenua desse grafico levaria a gestao a
    declarar uma melhoria que nao ocorreu.

    A correcao adotada tem duas partes:

    1. Mede-se a evasao ocorrida ate ``janela_dias`` apos a matricula, e nao a
       evasao acumulada total. Todas as coortes passam a ser avaliadas sobre o
       mesmo intervalo de exposicao.
    2. Excluem-se as coortes que ainda nao completaram a janela ate a data de
       referencia, pois para elas a medida seria estruturalmente incompleta.

    Args:
        df: base analitica.
        janela_dias: intervalo de observacao aplicado a todas as coortes.
        minimo_alunos: tamanho minimo da coorte para que a taxa seja exibida.

    Returns:
        DataFrame indexado pela coorte, com a taxa de evasao na janela.
    """
    referencia = pd.Timestamp(BUSINESS.data_referencia)
    base = df.copy()

    # Somente coortes que completaram a janela de observacao sao comparaveis.
    base["coorte_madura"] = (
        base["data_matricula"] + pd.Timedelta(days=janela_dias)
    ) <= referencia
    base = base.loc[base["coorte_madura"]]

    if base.empty:
        return pd.DataFrame(columns=["alunos", "evasoes", "taxa"])

    # Evasao considerada apenas se ocorrida dentro da janela.
    base["evadiu_na_janela"] = base["evadiu"] & (base["dias_vinculo"] <= janela_dias)

    coorte = (
        base.groupby("coorte_mes", observed=True)
        .agg(alunos=("id_aluno", "count"), evasoes=("evadiu_na_janela", "sum"))
        .sort_index()
    )
    coorte = coorte.loc[coorte["alunos"] >= minimo_alunos]
    coorte["taxa"] = coorte["evasoes"] / coorte["alunos"] * 100
    return coorte


def grafico_linhas_evolucao_churn(
    df: pd.DataFrame, destino: Path, janela_dias: int = 90
) -> Path:
    """Evolucao da taxa de evasao por coorte, sob janela fixa de observacao."""
    coorte = calcular_coorte_janela_fixa(df, janela_dias=janela_dias)
    if coorte.empty:
        raise ValueError("Nenhuma coorte madura disponivel para a janela informada.")

    fig, ax = plt.subplots(figsize=VIZ.figsize_largo)
    ax.plot(
        coorte.index,
        coorte["taxa"],
        marker="o",
        markersize=5,
        linewidth=2.0,
        color=VIZ.cor_alerta,
        label=f"Evasao ate {janela_dias} dias da matricula",
    )

    if len(coorte) >= 3:
        media_movel = coorte["taxa"].rolling(window=3, min_periods=2).mean()
        ax.plot(
            coorte.index,
            media_movel,
            linewidth=2.2,
            linestyle="--",
            color=VIZ.cor_secundaria,
            label="Media movel (3 coortes)",
        )

    media_periodo = float(coorte["evasoes"].sum() / coorte["alunos"].sum() * 100)
    ax.axhline(
        media_periodo,
        color=VIZ.cor_primaria,
        linestyle=":",
        linewidth=1.5,
        label=f"Media do periodo: {media_periodo:.1f}%",
    )

    ax.set_title(
        f"Evasao por Coorte de Matricula sob Janela Fixa de {janela_dias} Dias"
    )
    ax.set_xlabel("Coorte (mes de matricula)")
    ax.set_ylabel(f"Evasao ate {janela_dias} dias (%)")
    ax.legend(loc="best")
    ax.tick_params(axis="x", rotation=60)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

    ax.annotate(
        "Coortes sem janela completa foram excluidas para evitar vies de censura a direita.",
        xy=(0.005, -0.30),
        xycoords="axes fraction",
        fontsize=8.5,
        style="italic",
        color=VIZ.cor_neutra,
    )

    return _salvar(fig, "02_linhas_evolucao_churn", destino)


def grafico_dispersao_frequencia_app(df: pd.DataFrame, destino: Path) -> Path:
    """Relacao entre frequencia presencial e engajamento digital."""
    fig, ax = plt.subplots(figsize=VIZ.figsize_padrao)

    for evadiu, cor, rotulo in (
        (False, VIZ.cor_secundaria, "Retido"),
        (True, VIZ.cor_alerta, "Evadido"),
    ):
        recorte = df.loc[df["evadiu"] == evadiu]
        ax.scatter(
            recorte["frequencia_semanal"],
            recorte["checkins_app_mes"],
            s=17,
            alpha=0.45,
            color=cor,
            label=rotulo,
            edgecolors="none",
        )

    # Reta de tendencia por minimos quadrados sobre a base completa
    base = df[["frequencia_semanal", "checkins_app_mes"]].dropna()
    if len(base) > 2:
        coeficientes = np.polyfit(base["frequencia_semanal"], base["checkins_app_mes"], 1)
        eixo_x = np.linspace(
            base["frequencia_semanal"].min(), base["frequencia_semanal"].max(), 100
        )
        ax.plot(
            eixo_x,
            np.polyval(coeficientes, eixo_x),
            color=VIZ.cor_primaria,
            linewidth=2.0,
            linestyle="--",
            label="Tendencia linear",
        )

    ax.set_title("Frequencia Presencial versus Engajamento Digital")
    ax.set_xlabel("Frequencia semanal (dias)")
    ax.set_ylabel("Check-ins no aplicativo (mes)")
    ax.legend(loc="upper left")

    return _salvar(fig, "03_dispersao_frequencia_app", destino)


def grafico_histograma_frequencia(df: pd.DataFrame, destino: Path) -> Path:
    """Distribuicao da frequencia semanal com medidas de tendencia central."""
    serie = df["frequencia_semanal"].dropna()

    fig, ax = plt.subplots(figsize=VIZ.figsize_padrao)
    ax.hist(
        serie,
        bins=28,
        color=VIZ.cor_secundaria,
        alpha=0.78,
        edgecolor="white",
        linewidth=0.7,
    )

    for valor, cor, rotulo in (
        (serie.mean(), VIZ.cor_alerta, f"Media: {serie.mean():.2f}"),
        (serie.median(), VIZ.cor_sucesso, f"Mediana: {serie.median():.2f}"),
        (
            BUSINESS.frequencia_alvo_semanal,
            VIZ.cor_primaria,
            f"Limiar alvo: {BUSINESS.frequencia_alvo_semanal:.0f}",
        ),
    ):
        ax.axvline(valor, color=cor, linestyle="--", linewidth=1.8, label=rotulo)

    ax.set_title("Distribuicao da Frequencia Semanal de Comparecimento")
    ax.set_xlabel("Frequencia semanal (dias)")
    ax.set_ylabel("Numero de alunos")
    ax.legend(loc="upper right")

    return _salvar(fig, "04_histograma_frequencia", destino)


def grafico_boxplot_frequencia_status(df: pd.DataFrame, destino: Path) -> Path:
    """Distribuicao da frequencia semanal por status do contrato."""
    fig, ax = plt.subplots(figsize=VIZ.figsize_padrao)

    dados = [
        df.loc[~df["evadiu"], "frequencia_semanal"].dropna(),
        df.loc[df["evadiu"], "frequencia_semanal"].dropna(),
    ]

    caixas = ax.boxplot(
        dados,
        tick_labels=[f"Retido (n={len(dados[0])})", f"Evadido (n={len(dados[1])})"],
        patch_artist=True,
        widths=0.5,
        medianprops={"color": VIZ.cor_primaria, "linewidth": 2.0},
        flierprops={
            "marker": "o",
            "markersize": 4,
            "markerfacecolor": VIZ.cor_neutra,
            "markeredgecolor": "none",
            "alpha": 0.55,
        },
    )
    for caixa, cor in zip(caixas["boxes"], (VIZ.cor_secundaria, VIZ.cor_alerta)):
        caixa.set_facecolor(cor)
        caixa.set_alpha(0.62)

    ax.set_title("Frequencia Semanal por Status do Contrato")
    ax.set_ylabel("Frequencia semanal (dias)")

    return _salvar(fig, "05_boxplot_frequencia_status", destino)


def grafico_heatmap_correlacao(
    df: pd.DataFrame, variaveis: list[str], destino: Path
) -> Path:
    """Matriz de correlacao de Spearman entre as variaveis continuas."""
    presentes = [v for v in variaveis if v in df.columns]
    matriz = df[presentes].apply(pd.to_numeric, errors="coerce").corr(method="spearman")

    # A matriz e simetrica: exibir apenas o triangulo inferior elimina a
    # repeticao de informacao e reduz a carga de leitura.
    mascara = np.triu(np.ones_like(matriz, dtype=bool), k=1)

    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    sns.heatmap(
        matriz,
        mask=mascara,
        annot=True,
        fmt=".2f",
        cmap=VIZ.paleta_divergente,
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.7,
        linecolor="white",
        cbar_kws={"label": "Coeficiente de Spearman", "shrink": 0.78},
        ax=ax,
    )
    ax.set_title("Matriz de Correlacao de Spearman", pad=14)
    ax.tick_params(axis="x", rotation=38)
    ax.tick_params(axis="y", rotation=0)

    return _salvar(fig, "06_heatmap_correlacao", destino)


def grafico_pareto_receita(df: pd.DataFrame, destino: Path) -> Path:
    """Concentracao da receita acumulada por decil de aluno."""
    receita = df["receita_acumulada"].sort_values(ascending=False).reset_index(drop=True)
    if receita.empty or receita.sum() == 0:
        raise ValueError("Receita acumulada indisponivel para o grafico de Pareto.")

    n_decis = 10
    tamanho = int(np.ceil(len(receita) / n_decis))
    decis = [receita.iloc[i * tamanho : (i + 1) * tamanho].sum() for i in range(n_decis)]
    decis = np.array(decis)
    participacao = decis / decis.sum() * 100
    acumulado = np.cumsum(participacao)
    rotulos = [f"D{i + 1}" for i in range(n_decis)]

    fig, ax = plt.subplots(figsize=VIZ.figsize_largo)
    ax.bar(rotulos, participacao, color=VIZ.cor_secundaria, alpha=0.85, width=0.62)
    ax.set_xlabel("Decil de alunos, ordenado por receita acumulada (decrescente)")
    ax.set_ylabel("Participacao na receita (%)", color=VIZ.cor_secundaria)
    ax.set_ylim(0, max(participacao) * 1.25)

    eixo_secundario = ax.twinx()
    eixo_secundario.plot(
        rotulos,
        acumulado,
        color=VIZ.cor_alerta,
        marker="o",
        markersize=6,
        linewidth=2.2,
        label="Receita acumulada",
    )
    eixo_secundario.axhline(
        80, color=VIZ.cor_primaria, linestyle="--", linewidth=1.4, label="Referencia de 80%"
    )
    eixo_secundario.set_ylabel("Acumulado (%)", color=VIZ.cor_alerta)
    eixo_secundario.set_ylim(0, 108)
    eixo_secundario.grid(False)
    eixo_secundario.legend(loc="lower right")

    ax.set_title("Concentracao da Receita por Decil de Aluno (Principio de Pareto)")
    return _salvar(fig, "07_pareto_receita", destino)


def grafico_violino_vinculo_app(df: pd.DataFrame, destino: Path) -> Path:
    """Distribuicao do tempo de vinculo por adesao ao aplicativo."""
    base = df[["usa_app", "dias_vinculo"]].dropna().copy()
    base["Adesao ao aplicativo"] = np.where(base["usa_app"], "Com aplicativo", "Sem aplicativo")

    fig, ax = plt.subplots(figsize=VIZ.figsize_padrao)
    ordem = ["Sem aplicativo", "Com aplicativo"]
    sns.violinplot(
        data=base,
        x="Adesao ao aplicativo",
        y="dias_vinculo",
        hue="Adesao ao aplicativo",
        order=ordem,
        # hue_order deve ser declarado explicitamente: sem ele, o seaborn associa
        # a paleta a ordem alfabetica das categorias, e nao a ordem do eixo,
        # invertendo o significado das cores.
        hue_order=ordem,
        palette=[VIZ.cor_alerta, VIZ.cor_secundaria],
        # cut=0 trunca a estimativa de densidade nos valores efetivamente
        # observados. Sem essa restricao, a suavizacao projeta densidade em
        # tempo de vinculo negativo, situacao fisicamente impossivel.
        cut=0,
        inner="quartile",
        legend=False,
        ax=ax,
    )
    ax.set_title("Tempo de Vinculo por Adesao ao Aplicativo")
    ax.set_ylabel("Tempo de vinculo (dias)")
    ax.set_xlabel("")

    for i, categoria in enumerate([False, True]):
        mediana = base.loc[base["usa_app"] == categoria, "dias_vinculo"].median()
        ax.annotate(
            f"mediana: {mediana:.0f} dias",
            (i, mediana),
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=VIZ.cor_primaria,
            xytext=(0, 8),
            textcoords="offset points",
        )

    return _salvar(fig, "08_violino_vinculo_app", destino)


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------


def gerar_todos(
    df: pd.DataFrame, variaveis_correlacao: list[str], destino: Path = FIGURES_DIR
) -> dict[str, Path]:
    """
    Gera o conjunto completo de artefatos graficos.

    A falha na geracao de um grafico e registrada e nao interrompe os demais:
    em execucao automatizada, perder um artefato e preferivel a perder o
    relatorio inteiro.

    Returns:
        Mapeamento entre o nome do grafico e o caminho gravado.
    """
    aplicar_tema()

    tarefas = (
        ("barras", lambda: grafico_barras_churn_por_segmento(df, destino)),
        ("linhas", lambda: grafico_linhas_evolucao_churn(df, destino)),
        ("dispersao", lambda: grafico_dispersao_frequencia_app(df, destino)),
        ("histograma", lambda: grafico_histograma_frequencia(df, destino)),
        ("boxplot", lambda: grafico_boxplot_frequencia_status(df, destino)),
        ("heatmap", lambda: grafico_heatmap_correlacao(df, variaveis_correlacao, destino)),
        ("pareto", lambda: grafico_pareto_receita(df, destino)),
        ("violino", lambda: grafico_violino_vinculo_app(df, destino)),
    )

    gerados: dict[str, Path] = {}
    for nome, tarefa in tarefas:
        try:
            gerados[nome] = tarefa()
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Falha ao gerar o grafico '%s': %s", nome, exc)

    logger.info("Visualizacao concluida: %d de %d artefatos gerados.", len(gerados), len(tarefas))
    return gerados
