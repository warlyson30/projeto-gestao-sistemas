"""
Camada de transformacao (T do ETL).

Aplica, em ordem determinada, as regras de limpeza e enriquecimento que
convertem a base bruta em base analitica. A ordem das etapas nao e arbitraria:

    1. Normalizacao de tipos e texto  -> sem isto, a deduplicacao falha, pois
       "Mensal" e " mensal " seriam tratados como registros distintos.
    2. Deduplicacao                   -> executada antes da imputacao, para que
       estatisticas de imputacao (mediana, moda) nao sejam enviesadas por
       registros replicados.
    3. Validacao de dominio           -> valores impossiveis sao convertidos em
       nulo antes da imputacao, e nao depois, para que nao contaminem a mediana.
    4. Imputacao de ausentes          -> preenchimento com estrategia declarada
       por coluna.
    5. Deteccao de outliers           -> sinalizacao, nunca remocao silenciosa.
    6. Engenharia de atributos        -> derivacao das variaveis analiticas.

Inverter qualquer um desses passos produz resultado numericamente diferente.
Esse encadeamento e a razao pela qual a transformacao e um pipeline explicito,
e nao um conjunto de operacoes independentes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import BUSINESS, ETL
from src.etl.validate import (
    QualityLedger,
    detectar_outliers_iqr,
    mascara_fora_dominio_categorico,
    mascara_fora_dominio_numerico,
)
from src.logger import get_logger

logger = get_logger("etl.transform")


class DataLossError(RuntimeError):
    """Levantada quando a limpeza descarta volume de registros acima do tolerado."""


# ---------------------------------------------------------------------------
# Etapa 1: normalizacao
# ---------------------------------------------------------------------------


def _normalizar_texto(serie: pd.Series) -> pd.Series:
    """Remove espacos residuais e uniformiza a capitalizacao de categorias."""
    return (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.title()
    )


def _converter_datas(serie: pd.Series) -> pd.Series:
    """
    Converte datas em formatos heterogeneos para datetime.

    A base de origem mistura ISO (YYYY-MM-DD), oriundo do sistema atual, e
    formato brasileiro (DD/MM/YYYY), oriundo da migracao de legado. A conversao
    e feita em duas passagens explicitas, e nao com inferencia automatica,
    porque a inferencia interpretaria 03/04/2025 de forma ambigua conforme a
    ordem em que os registros aparecem no arquivo.
    """
    texto = serie.astype("string").str.strip()

    # Passagem 1: formato ISO
    convertido = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")

    # Passagem 2: formato brasileiro, apenas para o residuo nao convertido
    residuo = convertido.isna() & texto.notna()
    if residuo.any():
        convertido.loc[residuo] = pd.to_datetime(
            texto.loc[residuo], format="%d/%m/%Y", errors="coerce"
        )

    return convertido


def normalizar(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """Uniformiza tipos, textos e datas."""
    df = df.copy()

    # --- Categorias textuais ------------------------------------------------
    for coluna in ("plano", "unidade", "modalidade_principal"):
        original = df[coluna].astype("string")
        df[coluna] = _normalizar_texto(df[coluna])
        alterados = int((original.fillna("") != df[coluna].fillna("")).sum())
        ledger.registrar(
            etapa="normalizacao",
            regra="padronizacao_texto",
            coluna=coluna,
            registros_afetados=alterados,
            acao="trim + colapso de espacos + Title Case",
            justificativa=(
                "Digitacao livre no cadastro produz variacoes da mesma categoria "
                "(por exemplo 'mensal', 'MENSAL', ' Mensal '). Sem padronizacao, "
                "cada variacao seria contada como uma categoria distinta nas "
                "agregacoes e impediria a deduplicacao correta."
            ),
        )

    # --- Datas --------------------------------------------------------------
    for coluna in ("data_matricula", "data_cancelamento"):
        antes_nulos = int(df[coluna].isna().sum())
        df[coluna] = _converter_datas(df[coluna])
        depois_nulos = int(df[coluna].isna().sum())
        nao_parseados = depois_nulos - antes_nulos
        ledger.registrar(
            etapa="normalizacao",
            regra="conversao_datas_multiformato",
            coluna=coluna,
            registros_afetados=nao_parseados,
            acao="parse ISO e, no residuo, parse DD/MM/YYYY",
            justificativa=(
                "A base mistura o formato ISO do sistema atual com o formato "
                "brasileiro herdado da migracao de legado. A conversao em duas "
                "passagens explicitas elimina a ambiguidade de datas como "
                "03/04/2025, que a inferencia automatica resolveria de forma "
                "inconsistente entre linhas."
            ),
        )

    # --- Numericos ----------------------------------------------------------
    for coluna in ("valor_mensalidade", "idade", "frequencia_semanal", "checkins_app_mes"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    # --- Booleano -----------------------------------------------------------
    df["usa_app"] = (
        df["usa_app"]
        .astype("string")
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False, "sim": True, "nao": False})
        .astype("boolean")
    )

    return df


# ---------------------------------------------------------------------------
# Etapa 2: deduplicacao
# ---------------------------------------------------------------------------


def deduplicar(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Remove registros replicados.

    A deduplicacao ocorre em dois niveis. O primeiro elimina linhas
    integralmente identicas, tipicamente originadas de reenvio de lote na
    integracao. O segundo trata a chave de negocio ``id_aluno``: um mesmo aluno
    nao pode ocupar duas linhas na base analitica, sob pena de ser contado duas
    vezes em todo KPI de carteira.
    """
    df = df.copy()

    n_antes = len(df)
    df = df.drop_duplicates(keep="first")
    exatas = n_antes - len(df)
    ledger.registrar(
        etapa="deduplicacao",
        regra="linhas_integralmente_duplicadas",
        coluna="<todas>",
        registros_afetados=exatas,
        acao="descarte mantendo a primeira ocorrencia",
        justificativa=(
            "Reenvio de lote na integracao com o sistema de gestao replica "
            "linhas identicas. Mante-las inflaria artificialmente o tamanho da "
            "carteira e o faturamento agregado."
        ),
    )

    n_antes = len(df)
    # Ordena por completude decrescente para que, entre duplicatas da mesma
    # chave, prevaleca o registro com menos campos ausentes.
    df = df.assign(_completude=df.notna().sum(axis=1))
    df = (
        df.sort_values(["id_aluno", "_completude"], ascending=[True, False])
        .drop_duplicates(subset=["id_aluno"], keep="first")
        .drop(columns="_completude")
    )
    por_chave = n_antes - len(df)
    ledger.registrar(
        etapa="deduplicacao",
        regra="chave_de_negocio_duplicada",
        coluna="id_aluno",
        registros_afetados=por_chave,
        acao="mantido o registro mais completo por id_aluno",
        justificativa=(
            "id_aluno e a chave primaria da carteira. Registros duplicados nesta "
            "chave provocariam dupla contagem em todos os indicadores de base "
            "ativa, receita e evasao. Entre duplicatas, preserva-se o registro "
            "com maior numero de campos preenchidos."
        ),
    )

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Etapa 3: validacao de dominio
# ---------------------------------------------------------------------------


def aplicar_dominio(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Converte valores fora do dominio fisico ou de negocio em ausentes.

    A conversao em nulo, e nao o descarte da linha, e deliberada: uma idade
    registrada como 999 invalida aquele campo, mas nao invalida o historico de
    frequencia, o plano contratado ou a data de matricula do mesmo aluno.
    Descartar a linha inteira destruiria informacao valida.
    """
    df = df.copy()

    regras_numericas = {
        "idade": (
            BUSINESS.idade_min,
            BUSINESS.idade_max,
            "Idade fora do intervalo admissivel para matricula (16 a 89 anos). "
            "Valores como 0, 1 ou 999 sao erro de lancamento manual na recepcao.",
        ),
        "valor_mensalidade": (
            BUSINESS.mensalidade_min,
            BUSINESS.mensalidade_max,
            "Mensalidade negativa ou acima do teto comercial indica erro de sinal "
            "ou de digitacao. Manter valores negativos reduziria artificialmente "
            "a receita agregada.",
        ),
        "frequencia_semanal": (
            BUSINESS.frequencia_min,
            BUSINESS.frequencia_max,
            "A frequencia semanal e limitada fisicamente a 7 dias. Valores "
            "superiores indicam duplicidade de check-in na catraca.",
        ),
        "checkins_app_mes": (
            BUSINESS.checkins_app_min,
            None,
            "Contagem de check-ins nao admite valor negativo.",
        ),
    }

    for coluna, (minimo, maximo, justificativa) in regras_numericas.items():
        mascara = mascara_fora_dominio_numerico(df[coluna], minimo, maximo)
        n = int(mascara.sum())
        if n:
            df.loc[mascara, coluna] = np.nan
        ledger.registrar(
            etapa="validacao_dominio",
            regra="intervalo_numerico_admissivel",
            coluna=coluna,
            registros_afetados=n,
            acao="valor convertido em ausente para imputacao posterior",
            justificativa=justificativa,
        )

    regras_categoricas = {
        "plano": BUSINESS.planos_validos,
        "unidade": BUSINESS.unidades_validas,
        "modalidade_principal": BUSINESS.modalidades_validas,
    }

    for coluna, validos in regras_categoricas.items():
        mascara = mascara_fora_dominio_categorico(df[coluna], validos)
        n = int(mascara.sum())
        if n:
            df.loc[mascara, coluna] = pd.NA
        ledger.registrar(
            etapa="validacao_dominio",
            regra="categoria_fora_do_dominio",
            coluna=coluna,
            registros_afetados=n,
            acao="valor convertido em ausente",
            justificativa=(
                f"Apenas as categorias {list(validos)} sao comercializadas ou "
                "operadas. Categorias divergentes remanescentes apos a "
                "padronizacao textual indicam erro de origem."
            ),
        )

    # --- Coerencia temporal -------------------------------------------------
    incoerente = (
        df["data_cancelamento"].notna()
        & df["data_matricula"].notna()
        & (df["data_cancelamento"] < df["data_matricula"])
    )
    n = int(incoerente.sum())
    if n:
        df.loc[incoerente, "data_cancelamento"] = pd.NaT
    ledger.registrar(
        etapa="validacao_dominio",
        regra="coerencia_temporal",
        coluna="data_cancelamento",
        registros_afetados=n,
        acao="cancelamento anterior a matricula anulado",
        justificativa=(
            "Um cancelamento nao pode preceder a matricula. A inversao indica "
            "erro de preenchimento e distorceria o calculo de tempo de vida do "
            "aluno, base do indicador de retencao."
        ),
    )

    return df


# ---------------------------------------------------------------------------
# Etapa 4: registros irrecuperaveis e imputacao
# ---------------------------------------------------------------------------


def descartar_irrecuperaveis(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Descarta registros sem os campos criticos que definem a identidade comercial.

    Ao contrario da validacao de dominio, aqui o descarte da linha e a unica
    saida possivel: sem plano, sem valor de mensalidade ou sem data de
    matricula, o registro nao pode compor nenhum indicador de carteira, e
    imputar esses campos equivaleria a inventar contratos inexistentes.
    """
    n_antes = len(df)
    df = df.dropna(subset=list(ETL.colunas_criticas)).reset_index(drop=True)
    descartados = n_antes - len(df)

    ledger.registrar(
        etapa="descarte",
        regra="campos_criticos_ausentes",
        coluna=", ".join(ETL.colunas_criticas),
        registros_afetados=descartados,
        acao="registro removido da base analitica",
        justificativa=(
            "Os campos criticos definem a existencia comercial do contrato. "
            "Imputar plano ou valor de mensalidade criaria receita ficticia e "
            "comprometeria todos os KPIs financeiros derivados."
        ),
    )
    return df


def imputar(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Preenche valores ausentes com estrategia declarada e justificada por coluna.

    Tres estrategias sao empregadas:

    - Mediana, para variaveis numericas continuas assimetricas. A media seria
      deslocada pelos proprios extremos que se pretende preservar na analise.
    - Moda, para variaveis categoricas, por ser a unica medida de tendencia
      central definida em escala nominal.
    - Constante zero, para contagens em que a ausencia possui significado de
      negocio conhecido (ausencia de check-in equivale a zero check-in).
    """
    df = df.copy()

    for coluna in ETL.imputacao_mediana:
        n = int(df[coluna].isna().sum())
        if n:
            valor = float(df[coluna].median())
            df[coluna] = df[coluna].fillna(valor)
            detalhe = f"mediana = {valor:.2f}"
        else:
            detalhe = "sem ausentes"
        ledger.registrar(
            etapa="imputacao",
            regra="imputacao_por_mediana",
            coluna=coluna,
            registros_afetados=n,
            acao=f"preenchimento com {detalhe}",
            justificativa=(
                "Variavel continua com distribuicao assimetrica. A mediana e "
                "robusta a valores extremos, enquanto a media seria deslocada "
                "pelos proprios outliers que a analise pretende investigar."
            ),
        )

    for coluna in ETL.imputacao_moda:
        n = int(df[coluna].isna().sum())
        if n:
            modas = df[coluna].mode(dropna=True)
            valor = modas.iloc[0] if len(modas) else "Nao Informado"
            df[coluna] = df[coluna].fillna(valor)
            detalhe = f"moda = {valor}"
        else:
            detalhe = "sem ausentes"
        ledger.registrar(
            etapa="imputacao",
            regra="imputacao_por_moda",
            coluna=coluna,
            registros_afetados=n,
            acao=f"preenchimento com {detalhe}",
            justificativa=(
                "Variavel categorica nominal. A moda e a unica medida de "
                "tendencia central definida nesta escala de mensuracao."
            ),
        )

    for coluna in ETL.imputacao_zero:
        n = int(df[coluna].isna().sum())
        if n:
            df[coluna] = df[coluna].fillna(0)
        ledger.registrar(
            etapa="imputacao",
            regra="imputacao_por_constante",
            coluna=coluna,
            registros_afetados=n,
            acao="preenchimento com 0",
            justificativa=(
                "A ausencia de registro de check-in no aplicativo possui "
                "significado de negocio conhecido: representa nenhum check-in "
                "realizado, e nao informacao desconhecida."
            ),
        )

    # usa_app: ausencia tratada como nao adesao, coerente com a regra acima.
    n = int(df["usa_app"].isna().sum())
    if n:
        df["usa_app"] = df["usa_app"].fillna(False)
    df["usa_app"] = df["usa_app"].astype(bool)
    ledger.registrar(
        etapa="imputacao",
        regra="imputacao_por_constante",
        coluna="usa_app",
        registros_afetados=n,
        acao="preenchimento com False",
        justificativa=(
            "Ausencia de vinculo registrado no aplicativo e interpretada como "
            "nao adesao, mantendo coerencia com o tratamento de checkins_app_mes."
        ),
    )

    return df


# ---------------------------------------------------------------------------
# Etapa 5: outliers
# ---------------------------------------------------------------------------


def sinalizar_outliers(
    df: pd.DataFrame,
    ledger: QualityLedger,
    colunas: tuple[str, ...] | None = None,
    etapa: str = "outliers_origem",
    coluna_resumo: str = "outlier_qualquer",
) -> pd.DataFrame:
    """
    Identifica outliers pelo criterio IQR e os sinaliza em colunas dedicadas.

    A funcao e aplicada em duas passagens com finalidades distintas:

    - Sobre as colunas de origem, o extremo levanta suspeita de defeito de
      captura no sistema transacional (lente de qualidade de dados).
    - Sobre as colunas derivadas, o extremo representa comportamento comercial
      real e relevante, como o aluno de altissimo valor acumulado (lente
      analitica).

    A estrategia e sinalizar, nunca remover. Em uma academia, o aluno de
    frequencia ou ticket extremo e o ativo comercial mais valioso da carteira:
    exclui-lo suprimiria justamente a evidencia que sustenta a hipotese de
    retencao investigada no projeto.
    """
    df = df.copy()
    colunas = colunas if colunas is not None else ETL.colunas_outlier
    colunas_flag: list[str] = []

    for coluna in colunas:
        mascara, limites = detectar_outliers_iqr(
            df[coluna], ETL.outlier_iqr_multiplicador
        )
        flag = f"outlier_{coluna}"
        df[flag] = mascara.astype(bool)
        colunas_flag.append(flag)

        detalhe = (
            f"limites [{limites.get('limite_inferior')}, {limites.get('limite_superior')}]"
            if limites
            else "amostra insuficiente"
        )
        ledger.registrar(
            etapa=etapa,
            regra="criterio_iqr_tukey",
            coluna=coluna,
            registros_afetados=int(mascara.sum()),
            acao=f"sinalizado em {flag} ({detalhe})",
            justificativa=(
                "O criterio IQR nao pressupoe normalidade e seus limites nao sao "
                "influenciados pelos proprios extremos, ao contrario do z-score. "
                "Os outliers sao sinalizados e nao removidos: em uma academia, o "
                "aluno de frequencia ou ticket extremo e o ativo comercial mais "
                "valioso da carteira, e sua exclusao suprimiria a evidencia "
                "central da hipotese de retencao."
            ),
        )

    df[coluna_resumo] = df[colunas_flag].any(axis=1) if colunas_flag else False
    return df


# ---------------------------------------------------------------------------
# Etapa 6: engenharia de atributos
# ---------------------------------------------------------------------------


def derivar_atributos(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Constroi as variaveis analiticas consumidas pelos KPIs e pela estatistica.

    Nenhuma destas colunas existe no sistema de origem: todas sao derivadas de
    regra de negocio explicita e constituem a ponte entre o dado transacional e
    o indicador gerencial.
    """
    df = df.copy()
    referencia = pd.Timestamp(BUSINESS.data_referencia)

    # Status do contrato
    df["evadiu"] = df["data_cancelamento"].notna()
    df["status"] = np.where(df["evadiu"], "Cancelado", "Ativo")

    # Tempo de vida do aluno em dias (lifetime).
    # Para o aluno ativo, mede-se ate a data de referencia da analise.
    fim_vinculo = df["data_cancelamento"].fillna(referencia)
    df["dias_vinculo"] = (fim_vinculo - df["data_matricula"]).dt.days.clip(lower=0)
    df["meses_vinculo"] = (df["dias_vinculo"] / 30.44).round(2)

    # Evasao precoce: cancelamento dentro da janela critica definida no TAP.
    df["evasao_precoce"] = df["evadiu"] & (
        df["dias_vinculo"] <= BUSINESS.janela_evasao_critica_dias
    )

    # Receita realizada por aluno ao longo do vinculo (proxy de LTV).
    df["receita_acumulada"] = (df["valor_mensalidade"] * df["meses_vinculo"]).round(2)

    # Coorte de matricula, base para a analise de tendencia temporal.
    df["coorte_mes"] = df["data_matricula"].dt.to_period("M").astype(str)

    # Faixa etaria, para segmentacao categorica.
    df["faixa_etaria"] = pd.cut(
        df["idade"],
        bins=[15, 24, 34, 44, 54, 90],
        labels=["16-24", "25-34", "35-44", "45-54", "55+"],
        right=True,
    ).astype("string")

    # Classificacao de engajamento, combinando frequencia e adesao digital.
    condicoes = [
        (df["frequencia_semanal"] >= BUSINESS.frequencia_alvo_semanal) & df["usa_app"],
        (df["frequencia_semanal"] >= BUSINESS.frequencia_alvo_semanal) & ~df["usa_app"],
        (df["frequencia_semanal"] < BUSINESS.frequencia_alvo_semanal) & df["usa_app"],
    ]
    df["segmento_engajamento"] = np.select(
        condicoes,
        ["Alto", "Medio-Presencial", "Medio-Digital"],
        default="Baixo",
    )

    novas = [
        "evadiu",
        "status",
        "dias_vinculo",
        "meses_vinculo",
        "evasao_precoce",
        "receita_acumulada",
        "coorte_mes",
        "faixa_etaria",
        "segmento_engajamento",
    ]
    ledger.registrar(
        etapa="feature_engineering",
        regra="derivacao_de_atributos_analiticos",
        coluna=", ".join(novas),
        registros_afetados=len(df),
        acao=f"{len(novas)} colunas derivadas",
        justificativa=(
            "Variaveis nao presentes no sistema transacional, construidas a "
            "partir de regra de negocio explicita. Constituem a ponte entre o "
            "registro operacional e os indicadores gerenciais: dias_vinculo "
            "sustenta a analise de retencao, evasao_precoce operacionaliza a "
            "janela critica definida no TAP e segmento_engajamento viabiliza o "
            "teste da hipotese central do projeto."
        ),
    )

    return df


# ---------------------------------------------------------------------------
# Higiene de tipos
# ---------------------------------------------------------------------------


def _restaurar_tipos_inteiros(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Restaura o tipo inteiro das contagens apos a imputacao.

    A presenca de valores ausentes forca o pandas a promover colunas inteiras
    para ponto flutuante. Uma vez concluida a imputacao, a promocao deixa de ser
    necessaria e o tipo original deve ser restabelecido: manter idade como
    33.0 em vez de 33 propaga ruido de formatacao para relatorios e graficos.
    """
    df = df.copy()
    colunas_inteiras = ("idade", "checkins_app_mes")
    convertidas: list[str] = []

    for coluna in colunas_inteiras:
        if coluna in df.columns and df[coluna].notna().all():
            df[coluna] = df[coluna].round().astype("int64")
            convertidas.append(coluna)

    ledger.registrar(
        etapa="higiene_tipos",
        regra="restauracao_tipo_inteiro",
        coluna=", ".join(convertidas) if convertidas else "<nenhuma>",
        registros_afetados=len(df) if convertidas else 0,
        acao="conversao de float64 para int64",
        justificativa=(
            "Colunas de contagem foram promovidas a ponto flutuante pela "
            "presenca de ausentes. Concluida a imputacao, o tipo inteiro e "
            "restabelecido para evitar propagacao de ruido de formatacao aos "
            "relatorios e artefatos graficos."
        ),
    )
    return df


# ---------------------------------------------------------------------------
# Orquestracao da transformacao
# ---------------------------------------------------------------------------


def transformar(df: pd.DataFrame, ledger: QualityLedger) -> pd.DataFrame:
    """
    Executa a sequencia completa de transformacao.

    Raises:
        DataLossError: se a limpeza descartar volume acima do limite tolerado,
            o que indicaria defeito sistemico na origem e nao ruido pontual.
    """
    ledger.registros_entrada = len(df)

    df = normalizar(df, ledger)
    df = deduplicar(df, ledger)
    df = aplicar_dominio(df, ledger)
    df = descartar_irrecuperaveis(df, ledger)
    df = imputar(df, ledger)

    # Primeira passagem: lente de qualidade sobre as variaveis de origem.
    df = sinalizar_outliers(
        df,
        ledger,
        colunas=ETL.colunas_outlier,
        etapa="outliers_origem",
        coluna_resumo="outlier_origem",
    )

    df = derivar_atributos(df, ledger)

    # Segunda passagem: lente analitica sobre as variaveis derivadas. Executada
    # apos a engenharia de atributos porque estas colunas nao existem antes dela.
    df = sinalizar_outliers(
        df,
        ledger,
        colunas=ETL.colunas_outlier_derivadas,
        etapa="outliers_derivadas",
        coluna_resumo="outlier_derivada",
    )

    df["outlier_qualquer"] = df["outlier_origem"] | df["outlier_derivada"]
    df = _restaurar_tipos_inteiros(df, ledger)

    ledger.registros_saida = len(df)

    if ledger.taxa_perda > ETL.limite_perda_registros:
        raise DataLossError(
            f"Perda de registros de {ledger.taxa_perda:.2%} excede o limite "
            f"tolerado de {ETL.limite_perda_registros:.2%}. A execucao foi "
            "interrompida: perda desta magnitude indica defeito sistemico na "
            "origem, e prosseguir produziria indicadores nao representativos."
        )

    logger.info(
        "Transformacao concluida: %d registros validos, %d colunas.",
        len(df),
        df.shape[1],
    )
    return df
