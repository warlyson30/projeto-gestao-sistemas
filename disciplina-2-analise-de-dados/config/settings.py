"""
Configuracao central do projeto Vertice Fit Analytics.

Centraliza caminhos, parametros de negocio, regras de validacao e a
rastreabilidade com os objetivos SMART definidos no TAP (Disciplina 1).

Nenhum valor de negocio deve ser codificado diretamente nos modulos de
processamento: toda constante relevante e declarada aqui para permitir
alteracao de cenario sem modificacao de codigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Caminhos do projeto
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
INTERIM_DIR: Final[Path] = DATA_DIR / "interim"
PROCESSED_DIR: Final[Path] = DATA_DIR / "processed"

REPORTS_DIR: Final[Path] = PROJECT_ROOT / "reports"
FIGURES_DIR: Final[Path] = REPORTS_DIR / "figures"
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"

RAW_FILE: Final[Path] = RAW_DIR / "base_alunos_raw.csv"
INTERIM_FILE: Final[Path] = INTERIM_DIR / "base_alunos_interim.parquet"
PROCESSED_FILE: Final[Path] = PROCESSED_DIR / "base_alunos_processed.csv"
QUALITY_REPORT_FILE: Final[Path] = REPORTS_DIR / "data_quality_report.json"
KPI_REPORT_FILE: Final[Path] = REPORTS_DIR / "kpi_report.json"
STATS_REPORT_FILE: Final[Path] = REPORTS_DIR / "statistical_report.json"


def ensure_directories() -> None:
    """Cria a arvore de diretorios necessaria a execucao do pipeline."""
    for directory in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        REPORTS_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Reprodutibilidade
# ---------------------------------------------------------------------------

RANDOM_SEED: Final[int] = 42


# ---------------------------------------------------------------------------
# Parametros de negocio da Academia Vertice Fit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BusinessRules:
    """Regras de negocio e limites fisicos aceitos para os dados."""

    # Janela de observacao da base
    data_inicio_operacao: str = "2024-01-01"
    data_referencia: str = "2025-12-31"

    # Planos comercializados e respectivos precos de tabela (R$/mes)
    planos_validos: tuple[str, ...] = ("Mensal", "Trimestral", "Anual")
    preco_tabela: dict[str, float] = field(
        default_factory=lambda: {"Mensal": 129.90, "Trimestral": 109.90, "Anual": 89.90}
    )

    # Modalidades oferecidas
    modalidades_validas: tuple[str, ...] = (
        "Musculacao",
        "Spinning",
        "Funcional",
        "Yoga",
        "Crossfit",
    )

    unidades_validas: tuple[str, ...] = ("Zona Leste", "Zona Oeste", "Centro")

    # Limites fisicos plausiveis (usados na validacao de dominio)
    idade_min: int = 16
    idade_max: int = 89
    frequencia_min: float = 0.0
    frequencia_max: float = 7.0
    checkins_app_min: int = 0
    mensalidade_min: float = 0.0
    mensalidade_max: float = 500.0

    # Regra de negocio: janela critica de evasao (dias)
    janela_evasao_critica_dias: int = 60

    # Limiar de frequencia considerado saudavel para retencao
    frequencia_alvo_semanal: float = 3.0


BUSINESS: Final[BusinessRules] = BusinessRules()


# ---------------------------------------------------------------------------
# Parametros de qualidade de dados (ETL)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ETLConfig:
    """Parametros que governam a etapa de transformacao."""

    # Colunas obrigatorias: registro sem estes campos e descartado
    colunas_criticas: tuple[str, ...] = (
        "id_aluno",
        "data_matricula",
        "plano",
        "valor_mensalidade",
    )

    # Estrategia de imputacao por coluna
    # mediana -> robusta a outliers; moda -> categoricas; constante -> dominio conhecido
    imputacao_mediana: tuple[str, ...] = ("frequencia_semanal", "idade")
    imputacao_moda: tuple[str, ...] = ("modalidade_principal", "unidade")
    imputacao_zero: tuple[str, ...] = ("checkins_app_mes",)

    # Deteccao de outliers pelo metodo IQR (Tukey)
    outlier_iqr_multiplicador: float = 1.5
    # Outliers sao sinalizados, nunca removidos silenciosamente:
    # a remocao exige justificativa de negocio explicita.
    outlier_estrategia: str = "flag"  # "flag" | "clip" | "drop"

    # Colunas de origem submetidas a analise de outlier (lente de qualidade:
    # o extremo pode indicar erro de captura no sistema transacional)
    colunas_outlier: tuple[str, ...] = (
        "frequencia_semanal",
        "valor_mensalidade",
        "checkins_app_mes",
    )

    # Colunas derivadas submetidas a analise de outlier (lente analitica: o
    # extremo e um comportamento de negocio real e relevante, nao um defeito)
    colunas_outlier_derivadas: tuple[str, ...] = (
        "receita_acumulada",
        "dias_vinculo",
    )

    # Percentual maximo de linhas descartaveis antes de abortar o pipeline
    limite_perda_registros: float = 0.20


ETL: Final[ETLConfig] = ETLConfig()


# ---------------------------------------------------------------------------
# Rastreabilidade com o TAP (Disciplina 1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SmartObjective:
    """Objetivo SMART declarado no Termo de Abertura do Projeto."""

    codigo: str
    descricao: str
    meta_numerica: str
    prazo: str


SMART_OBJECTIVES: Final[dict[str, SmartObjective]] = {
    "OE-01": SmartObjective(
        codigo="OE-01",
        descricao=(
            "Reduzir a taxa de evasao (churn) mensal de alunos da Academia "
            "Vertice Fit por meio de acoes de retencao baseadas em dados."
        ),
        meta_numerica="Reduzir o churn mensal em 10 pontos percentuais",
        prazo="3 meses apos a implantacao",
    ),
    "OE-02": SmartObjective(
        codigo="OE-02",
        descricao=(
            "Identificar antecipadamente a parcela da carteira com maior "
            "probabilidade de cancelamento, permitindo acao preventiva."
        ),
        meta_numerica="Classificar 20% da base como carteira de risco prioritario",
        prazo="3 meses apos a implantacao",
    ),
    "OE-03": SmartObjective(
        codigo="OE-03",
        descricao=(
            "Elevar o engajamento digital dos alunos no aplicativo proprio, "
            "hipotese central de alavanca de retencao."
        ),
        meta_numerica="Elevar a adesao ao aplicativo para 80% da base ativa",
        prazo="6 meses apos a implantacao",
    ),
    "OE-04": SmartObjective(
        codigo="OE-04",
        descricao=(
            "Otimizar a ocupacao da grade de aulas e a alocacao de instrutores, "
            "insumo direto do modelo de programacao linear da Disciplina 4."
        ),
        meta_numerica="Reduzir a ociosidade da grade em 15%",
        prazo="6 meses apos a implantacao",
    ),
}


# ---------------------------------------------------------------------------
# Parametros estatisticos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatsConfig:
    """Parametros dos testes de hipotese e criterios de interpretacao."""

    alpha: float = 0.05

    # Limite de amostra para o teste de Shapiro-Wilk.
    # Acima disso, Shapiro perde utilidade pratica (rejeita quase sempre) e
    # utiliza-se D'Agostino-Pearson.
    shapiro_max_n: int = 5000

    # Faixas de interpretacao do coeficiente de correlacao (valor absoluto)
    faixas_correlacao: tuple[tuple[float, str], ...] = (
        (0.00, "desprezivel"),
        (0.10, "fraca"),
        (0.30, "moderada"),
        (0.50, "forte"),
        (0.70, "muito forte"),
    )

    # Faixas de interpretacao do tamanho de efeito (d de Cohen)
    faixas_cohen_d: tuple[tuple[float, str], ...] = (
        (0.00, "desprezivel"),
        (0.20, "pequeno"),
        (0.50, "medio"),
        (0.80, "grande"),
    )

    # Limite de assimetria a partir do qual a distribuicao e considerada
    # relevantemente assimetrica (criterio de Bulmer)
    limite_assimetria_moderada: float = 0.5
    limite_assimetria_alta: float = 1.0


STATS: Final[StatsConfig] = StatsConfig()


# ---------------------------------------------------------------------------
# Parametros de visualizacao
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VizConfig:
    """Padrao visual unico para todos os artefatos graficos do projeto."""

    dpi: int = 150
    figsize_padrao: tuple[float, float] = (11.0, 6.0)
    figsize_largo: tuple[float, float] = (13.0, 6.5)
    formato_arquivo: str = "png"

    # Paleta corporativa (consistente entre todos os graficos)
    cor_primaria: str = "#1E293B"
    cor_secundaria: str = "#0EA5E9"
    cor_alerta: str = "#DC2626"
    cor_sucesso: str = "#16A34A"
    cor_atencao: str = "#D97706"
    cor_neutra: str = "#94A3B8"
    cor_grade: str = "#E2E8F0"

    paleta_sequencial: str = "YlOrRd"
    paleta_divergente: str = "RdBu_r"


VIZ: Final[VizConfig] = VizConfig()


# ---------------------------------------------------------------------------
# Geracao da base sintetica
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticDataConfig:
    """
    Parametros do gerador de base sintetica.

    A base e gerada com imperfeicoes deliberadas (nulos, duplicatas,
    inconsistencias de categoria, valores fora de dominio e datas em
    formatos mistos) para que a etapa de ETL exerca funcao real, e nao
    meramente decorativa.
    """

    n_alunos: int = 1500

    # Taxas de contaminacao aplicadas a base bruta
    taxa_nulos_frequencia: float = 0.06
    taxa_nulos_idade: float = 0.04
    taxa_nulos_modalidade: float = 0.05
    taxa_nulos_checkins: float = 0.07
    taxa_duplicatas: float = 0.03
    taxa_categoria_suja: float = 0.12
    taxa_valor_negativo: float = 0.015
    taxa_idade_absurda: float = 0.01
    taxa_data_formato_alternativo: float = 0.15


SYNTHETIC: Final[SyntheticDataConfig] = SyntheticDataConfig()
