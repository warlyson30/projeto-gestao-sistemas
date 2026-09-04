"""
Catalogo de indicadores-chave de desempenho (KPI).

Este modulo implementa o requisito central da entrega: nenhum KPI e arbitrario.
Cada indicador declara explicitamente:

- a formula de calculo;
- a unidade e a direcao desejada (se aumentar ou diminuir e favoravel);
- o objetivo SMART do TAP cuja evolucao ele mede;
- a justificativa tecnica de sua existencia.

O padrao adotado e o de registro (registry): a definicao do indicador e o seu
calculo residem na mesma estrutura, de modo que e impossivel adicionar um KPI
ao relatorio sem simultaneamente declarar por que ele existe e a qual meta
responde. Essa restricao estrutural e deliberada: ela impede a proliferacao de
metricas sem proposito, problema recorrente em paineis gerenciais.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from config.settings import BUSINESS, SMART_OBJECTIVES

# ---------------------------------------------------------------------------
# Estrutura de definicao
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KPIDefinition:
    """Definicao completa e autocontida de um indicador."""

    codigo: str
    nome: str
    formula: str
    unidade: str
    direcao_desejada: str  # "minimizar" | "maximizar" | "monitorar"
    objetivo_smart: str
    justificativa: str
    calculo: Callable[[pd.DataFrame], float]

    def avaliar(self, df: pd.DataFrame) -> float:
        """Executa o calculo protegendo contra base vazia."""
        if df.empty:
            return float("nan")
        return float(self.calculo(df))

    @property
    def objetivo_descricao(self) -> str:
        objetivo = SMART_OBJECTIVES.get(self.objetivo_smart)
        return objetivo.descricao if objetivo else "Nao vinculado"

    @property
    def objetivo_meta(self) -> str:
        objetivo = SMART_OBJECTIVES.get(self.objetivo_smart)
        return objetivo.meta_numerica if objetivo else "Nao definida"


# ---------------------------------------------------------------------------
# Funcoes de calculo
# ---------------------------------------------------------------------------


def _taxa_churn(df: pd.DataFrame) -> float:
    return df["evadiu"].mean() * 100


def _taxa_evasao_precoce(df: pd.DataFrame) -> float:
    """Proporcao de evasoes ocorridas dentro da janela critica, sobre o total de evasoes."""
    evadidos = df.loc[df["evadiu"]]
    if evadidos.empty:
        return 0.0
    return evadidos["evasao_precoce"].mean() * 100


def _ticket_medio(df: pd.DataFrame) -> float:
    return df["valor_mensalidade"].mean()


def _receita_recorrente_mensal(df: pd.DataFrame) -> float:
    """Soma das mensalidades da carteira ativa (MRR)."""
    return df.loc[~df["evadiu"], "valor_mensalidade"].sum()


def _frequencia_media(df: pd.DataFrame) -> float:
    return df["frequencia_semanal"].mean()


def _taxa_adesao_app(df: pd.DataFrame) -> float:
    ativos = df.loc[~df["evadiu"]]
    if ativos.empty:
        return 0.0
    return ativos["usa_app"].mean() * 100


def _permanencia_media_meses(df: pd.DataFrame) -> float:
    """Tempo medio de vinculo dos alunos que ja encerraram o contrato."""
    evadidos = df.loc[df["evadiu"]]
    if evadidos.empty:
        return float("nan")
    return evadidos["meses_vinculo"].mean()


def carteira_de_risco(df: pd.DataFrame) -> pd.Series:
    """
    Define a mascara da carteira de risco prioritario.

    O criterio combina os dois fatores protetivos identificados na analise
    estatistica: ausencia de adesao digital e frequencia semanal abaixo do
    limiar considerado saudavel para a retencao. E deliberadamente simples e
    auditavel, para que a equipe de recepcao consiga aplica-lo sem depender de
    modelo preditivo.
    """
    return (~df["usa_app"]) & (df["frequencia_semanal"] < BUSINESS.frequencia_alvo_semanal)


def _percentual_carteira_risco(df: pd.DataFrame) -> float:
    ativos = df.loc[~df["evadiu"]]
    if ativos.empty:
        return 0.0
    return carteira_de_risco(ativos).mean() * 100


def _receita_em_risco(df: pd.DataFrame) -> float:
    """MRR atribuivel a carteira de risco prioritario."""
    ativos = df.loc[~df["evadiu"]]
    if ativos.empty:
        return 0.0
    return ativos.loc[carteira_de_risco(ativos), "valor_mensalidade"].sum()


def _taxa_subutilizacao(df: pd.DataFrame) -> float:
    """Proporcao da carteira ativa com frequencia abaixo do limiar alvo."""
    ativos = df.loc[~df["evadiu"]]
    if ativos.empty:
        return 0.0
    return (ativos["frequencia_semanal"] < BUSINESS.frequencia_alvo_semanal).mean() * 100


def _ltv_medio(df: pd.DataFrame) -> float:
    """Valor medio ja realizado por aluno ao longo do vinculo."""
    return df["receita_acumulada"].mean()


def _concentracao_receita_top20(df: pd.DataFrame) -> float:
    """
    Percentual da receita acumulada concentrado nos 20% maiores contratos.

    Operacionaliza o principio de Pareto sobre a carteira: quanto maior o
    indice, maior a exposicao do faturamento a um numero reduzido de alunos.
    """
    receita = df["receita_acumulada"].sort_values(ascending=False)
    if receita.empty or receita.sum() == 0:
        return 0.0
    corte = max(1, int(np.ceil(len(receita) * 0.20)))
    return receita.iloc[:corte].sum() / receita.sum() * 100


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

CATALOGO_KPI: tuple[KPIDefinition, ...] = (
    KPIDefinition(
        codigo="KPI-01",
        nome="Taxa de Evasao (Churn) da Carteira",
        formula="(alunos com cancelamento registrado / total de alunos) x 100",
        unidade="%",
        direcao_desejada="minimizar",
        objetivo_smart="OE-01",
        justificativa=(
            "Indicador primario do projeto. Mede diretamente a grandeza que o "
            "objetivo OE-01 se compromete a reduzir em dez pontos percentuais. "
            "Sem ele nao existe linha de base contra a qual aferir o sucesso da "
            "iniciativa, e a meta declarada no TAP permaneceria inverificavel."
        ),
        calculo=_taxa_churn,
    ),
    KPIDefinition(
        codigo="KPI-02",
        nome="Taxa de Evasao Precoce",
        formula=(
            "(cancelamentos ocorridos ate 60 dias da matricula / total de "
            "cancelamentos) x 100"
        ),
        unidade="%",
        direcao_desejada="minimizar",
        objetivo_smart="OE-02",
        justificativa=(
            "Decompoe o churn total segundo a janela critica de sessenta dias "
            "definida no TAP. A distincao e operacionalmente decisiva: a evasao "
            "precoce indica falha de integracao e experiencia inicial, "
            "corrigivel por processo de acolhimento, enquanto a evasao tardia "
            "remete a perda de valor percebido ao longo do tempo. Sao problemas "
            "distintos e exigem intervencoes distintas."
        ),
        calculo=_taxa_evasao_precoce,
    ),
    KPIDefinition(
        codigo="KPI-03",
        nome="Ticket Medio Mensal",
        formula="media aritmetica do valor de mensalidade praticado",
        unidade="R$",
        direcao_desejada="monitorar",
        objetivo_smart="OE-01",
        justificativa=(
            "Converte a evasao em impacto financeiro. Sem o ticket medio, uma "
            "reducao percentual de churn permanece uma abstracao estatistica; "
            "com ele, cada ponto percentual de retencao e traduzido em receita "
            "preservada, insumo direto da analise de viabilidade do projeto."
        ),
        calculo=_ticket_medio,
    ),
    KPIDefinition(
        codigo="KPI-04",
        nome="Receita Recorrente Mensal (MRR)",
        formula="somatorio das mensalidades da carteira ativa",
        unidade="R$/mes",
        direcao_desejada="maximizar",
        objetivo_smart="OE-01",
        justificativa=(
            "Estabelece a base financeira sobre a qual o retorno do projeto e "
            "calculado. O MRR e a grandeza que a evasao corroi mes a mes, e "
            "constitui o denominador do indicador de receita em risco."
        ),
        calculo=_receita_recorrente_mensal,
    ),
    KPIDefinition(
        codigo="KPI-05",
        nome="Frequencia Media Semanal",
        formula="media aritmetica de comparecimentos semanais por aluno",
        unidade="dias/semana",
        direcao_desejada="maximizar",
        objetivo_smart="OE-01",
        justificativa=(
            "Principal variavel comportamental antecedente a evasao. A hipotese "
            "estrutural do projeto e que a frequencia opera como fator protetivo "
            "da retencao; este KPI fornece a medida agregada cuja associacao com "
            "o churn e testada formalmente na etapa estatistica."
        ),
        calculo=_frequencia_media,
    ),
    KPIDefinition(
        codigo="KPI-06",
        nome="Taxa de Adesao ao Aplicativo",
        formula="(alunos ativos com uso do aplicativo / total de alunos ativos) x 100",
        unidade="%",
        direcao_desejada="maximizar",
        objetivo_smart="OE-03",
        justificativa=(
            "Mede o objetivo OE-03 e, simultaneamente, a alavanca de intervencao "
            "de menor custo marginal do projeto. Ao contrario da frequencia, que "
            "depende da disponibilidade do aluno, a adesao digital pode ser "
            "influenciada diretamente por acao da empresa, o que a torna a "
            "variavel de maior valor gerencial da analise."
        ),
        calculo=_taxa_adesao_app,
    ),
    KPIDefinition(
        codigo="KPI-07",
        nome="Permanencia Media do Aluno Evadido",
        formula="media de meses de vinculo entre os alunos que cancelaram",
        unidade="meses",
        direcao_desejada="maximizar",
        objetivo_smart="OE-01",
        justificativa=(
            "Complementa o churn com a dimensao temporal que a taxa isolada "
            "suprime. Duas carteiras podem apresentar identica taxa de evasao "
            "com desempenho economico distinto, conforme os alunos permanecam "
            "dois ou doze meses antes de cancelar. Esta metrica sustenta o "
            "calculo de valor de tempo de vida do cliente."
        ),
        calculo=_permanencia_media_meses,
    ),
    KPIDefinition(
        codigo="KPI-08",
        nome="Participacao da Carteira de Risco Prioritario",
        formula=(
            "(alunos ativos sem adesao ao aplicativo e com frequencia abaixo de "
            "3 dias por semana / total de alunos ativos) x 100"
        ),
        unidade="%",
        direcao_desejada="minimizar",
        objetivo_smart="OE-02",
        justificativa=(
            "Operacionaliza o objetivo OE-02, que exige a identificacao "
            "antecipada da parcela de maior propensao ao cancelamento. O criterio "
            "combina os dois fatores protetivos confirmados estatisticamente e "
            "foi mantido deliberadamente simples: a recepcao precisa conseguir "
            "aplica-lo sem dependencia de modelo preditivo ou infraestrutura "
            "adicional."
        ),
        calculo=_percentual_carteira_risco,
    ),
    KPIDefinition(
        codigo="KPI-09",
        nome="Receita Mensal em Risco",
        formula="somatorio das mensalidades da carteira de risco prioritario",
        unidade="R$/mes",
        direcao_desejada="minimizar",
        objetivo_smart="OE-02",
        justificativa=(
            "Traduz a carteira de risco em exposicao financeira mensurada. E o "
            "indicador que sustenta a priorizacao orcamentaria do projeto perante "
            "a alta administracao: o custo da acao de retencao passa a ser "
            "comparavel a receita que se deixaria de perder."
        ),
        calculo=_receita_em_risco,
    ),
    KPIDefinition(
        codigo="KPI-10",
        nome="Taxa de Subutilizacao da Estrutura",
        formula=(
            "(alunos ativos com frequencia inferior a 3 dias por semana / total "
            "de alunos ativos) x 100"
        ),
        unidade="%",
        direcao_desejada="minimizar",
        objetivo_smart="OE-04",
        justificativa=(
            "Vincula o comportamento do aluno a ocupacao da estrutura fisica. "
            "Fornece a estimativa de demanda reprimida que alimenta o modelo de "
            "programacao linear de alocacao de instrutores e grade de horarios "
            "desenvolvido na Disciplina 4, garantindo continuidade metodologica "
            "entre as etapas do projeto."
        ),
        calculo=_taxa_subutilizacao,
    ),
    KPIDefinition(
        codigo="KPI-11",
        nome="Valor Medio Realizado por Aluno",
        formula="media da receita acumulada ao longo do vinculo de cada aluno",
        unidade="R$",
        direcao_desejada="maximizar",
        objetivo_smart="OE-01",
        justificativa=(
            "Aproximacao do valor de tempo de vida do cliente construida com "
            "receita ja realizada, e nao projetada. A opcao pelo valor realizado "
            "e conservadora e deliberada: evita sustentar a justificativa "
            "economica do projeto sobre premissas de permanencia futura ainda "
            "nao verificadas."
        ),
        calculo=_ltv_medio,
    ),
    KPIDefinition(
        codigo="KPI-12",
        nome="Concentracao de Receita nos 20% Maiores Contratos",
        formula=(
            "(receita acumulada dos 20% maiores contratos / receita acumulada "
            "total) x 100"
        ),
        unidade="%",
        direcao_desejada="monitorar",
        objetivo_smart="OE-02",
        justificativa=(
            "Aplica o principio de Pareto a carteira para dimensionar a "
            "exposicao do faturamento a um numero reduzido de alunos. Quanto "
            "maior a concentracao, maior o impacto unitario de cada cancelamento "
            "no segmento de alto valor, o que redefine a prioridade das acoes de "
            "retencao: passa a importar nao apenas quantos alunos evadem, mas "
            "quais."
        ),
        calculo=_concentracao_receita_top20,
    ),
)
