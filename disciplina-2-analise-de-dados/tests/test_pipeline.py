"""
Suite de testes do pipeline analitico.

Os testes cobrem tres niveis distintos e complementares:

- Unitarios: verificam regras de limpeza isoladas com dados construidos
  especificamente para exercitar cada caso de borda.
- De contrato: garantem que as invariantes da base analitica se sustentam apos
  a transformacao, independentemente do conteudo de entrada.
- De integracao: executam o pipeline de ponta a ponta.

A cobertura prioriza as regras que, se quebradas silenciosamente, produziriam
numeros plausiveis porem incorretos. Um teste que apenas confirma que o codigo
executa sem excecao tem pouco valor: o risco real nao e o pipeline falhar de
forma visivel, e sim ele concluir com sucesso aparente sobre dados corrompidos.

Execucao:
    pytest tests/ -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config.settings import BUSINESS, ETL
from src.data_generation import gerar_base_bruta
from src.etl.transform import (
    DataLossError,
    aplicar_dominio,
    deduplicar,
    derivar_atributos,
    imputar,
    normalizar,
    transformar,
)
from src.etl.validate import QualityLedger, detectar_outliers_iqr
from src.kpi.definitions import CATALOGO_KPI, carteira_de_risco
from src.kpi.engine import calcular_kpis
from src.stats_engine.analysis import _cohen_d, _cramers_v, detectar_colinearidade
from src.stats_engine.plan import executar_analise


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base_bruta() -> pd.DataFrame:
    """Base bruta sintetica, com defeitos de qualidade presentes."""
    return gerar_base_bruta()


@pytest.fixture(scope="module")
def base_analitica(base_bruta: pd.DataFrame) -> pd.DataFrame:
    """Base processada pelo pipeline completo de transformacao."""
    return transformar(base_bruta.copy(), QualityLedger())


@pytest.fixture
def ledger() -> QualityLedger:
    return QualityLedger()


# ---------------------------------------------------------------------------
# Geracao de dados
# ---------------------------------------------------------------------------


class TestGeracaoDeDados:
    def test_reprodutibilidade_com_semente_fixa(self):
        """A mesma semente deve produzir bases identicas."""
        primeira = gerar_base_bruta(seed=7)
        segunda = gerar_base_bruta(seed=7)
        pd.testing.assert_frame_equal(primeira, segunda)

    def test_sementes_distintas_produzem_bases_distintas(self):
        primeira = gerar_base_bruta(seed=1)
        segunda = gerar_base_bruta(seed=2)
        assert not primeira.equals(segunda)

    def test_base_contem_defeitos_deliberados(self, base_bruta):
        """
        Sem defeitos na origem, o ETL nao teria funcao demonstravel e os testes
        de limpeza passariam por vacuidade.
        """
        assert base_bruta.isna().sum().sum() > 0, "esperada presenca de nulos"
        assert base_bruta.duplicated().sum() > 0, "esperada presenca de duplicatas"

        categorias = set(base_bruta["plano"].dropna().unique())
        assert not categorias.issubset(
            set(BUSINESS.planos_validos)
        ), "esperada presenca de categorias nao padronizadas"

    def test_idade_sem_acumulo_artificial_no_limite(self, base_bruta):
        """
        Regressao: a geracao por saturacao (clip) produzia pico artificial na
        idade minima, distorcendo histograma e assimetria.
        """
        idades = base_bruta["idade"].dropna()
        plausiveis = idades[(idades >= BUSINESS.idade_min) & (idades <= BUSINESS.idade_max)]
        contagem = plausiveis.value_counts()
        frequencia_no_minimo = contagem.get(float(BUSINESS.idade_min), 0)
        assert frequencia_no_minimo < contagem.max() * 0.5, (
            "acumulo excessivo na idade minima indica saturacao em vez de truncamento"
        )


# ---------------------------------------------------------------------------
# Normalizacao
# ---------------------------------------------------------------------------


class TestNormalizacao:
    def test_padroniza_variacoes_de_categoria(self, ledger):
        entrada = pd.DataFrame(
            {
                "plano": [" mensal ", "MENSAL", "Mensal", "anual"],
                "unidade": ["Centro"] * 4,
                "modalidade_principal": ["Musculacao"] * 4,
                "data_matricula": ["2024-01-01"] * 4,
                "data_cancelamento": [None] * 4,
                "valor_mensalidade": [100.0] * 4,
                "idade": [30] * 4,
                "frequencia_semanal": [3.0] * 4,
                "usa_app": ["True"] * 4,
                "checkins_app_mes": [5] * 4,
            }
        )
        resultado = normalizar(entrada, ledger)
        assert resultado["plano"].tolist() == ["Mensal", "Mensal", "Mensal", "Anual"]

    def test_converte_datas_em_formatos_mistos(self, ledger):
        """
        A base mistura ISO e formato brasileiro. A conversao em duas passagens
        deve resolver ambos sem ambiguidade.
        """
        entrada = pd.DataFrame(
            {
                "plano": ["Mensal"] * 3,
                "unidade": ["Centro"] * 3,
                "modalidade_principal": ["Musculacao"] * 3,
                "data_matricula": ["2024-03-15", "15/03/2024", "2024-12-01"],
                "data_cancelamento": [None] * 3,
                "valor_mensalidade": [100.0] * 3,
                "idade": [30] * 3,
                "frequencia_semanal": [3.0] * 3,
                "usa_app": ["True"] * 3,
                "checkins_app_mes": [5] * 3,
            }
        )
        resultado = normalizar(entrada, ledger)
        assert resultado["data_matricula"].isna().sum() == 0
        # As duas primeiras representam a mesma data em formatos diferentes.
        assert resultado["data_matricula"].iloc[0] == resultado["data_matricula"].iloc[1]


# ---------------------------------------------------------------------------
# Deduplicacao
# ---------------------------------------------------------------------------


class TestDeduplicacao:
    def test_remove_duplicatas_da_chave_de_negocio(self, ledger):
        entrada = pd.DataFrame(
            {
                "id_aluno": [1, 1, 2],
                "valor_mensalidade": [100.0, 100.0, 120.0],
                "idade": [30, 30, 40],
            }
        )
        resultado = deduplicar(entrada, ledger)
        assert resultado["id_aluno"].duplicated().sum() == 0
        assert len(resultado) == 2

    def test_preserva_o_registro_mais_completo(self, ledger):
        """
        Entre duplicatas da mesma chave, deve prevalecer o registro com menos
        campos ausentes, e nao simplesmente o primeiro encontrado.
        """
        entrada = pd.DataFrame(
            {
                "id_aluno": [1, 1],
                "valor_mensalidade": [np.nan, 120.0],
                "idade": [np.nan, 40],
            }
        )
        resultado = deduplicar(entrada, ledger)
        assert len(resultado) == 1
        assert resultado["valor_mensalidade"].iloc[0] == 120.0
        assert resultado["idade"].iloc[0] == 40


# ---------------------------------------------------------------------------
# Validacao de dominio
# ---------------------------------------------------------------------------


class TestValidacaoDeDominio:
    def _entrada_minima(self, **overrides) -> pd.DataFrame:
        base = {
            "idade": [30.0],
            "valor_mensalidade": [100.0],
            "frequencia_semanal": [3.0],
            "checkins_app_mes": [5.0],
            "plano": ["Mensal"],
            "unidade": ["Centro"],
            "modalidade_principal": ["Musculacao"],
            "data_matricula": [pd.Timestamp("2024-01-01")],
            "data_cancelamento": [pd.NaT],
        }
        base.update({k: [v] for k, v in overrides.items()})
        return pd.DataFrame(base)

    @pytest.mark.parametrize("idade_invalida", [0.0, 1.0, 150.0, 999.0])
    def test_anula_idade_fora_do_dominio(self, ledger, idade_invalida):
        resultado = aplicar_dominio(self._entrada_minima(idade=idade_invalida), ledger)
        assert pd.isna(resultado["idade"].iloc[0])

    def test_anula_mensalidade_negativa(self, ledger):
        resultado = aplicar_dominio(self._entrada_minima(valor_mensalidade=-129.9), ledger)
        assert pd.isna(resultado["valor_mensalidade"].iloc[0])

    def test_anula_cancelamento_anterior_a_matricula(self, ledger):
        entrada = self._entrada_minima(
            data_matricula=pd.Timestamp("2024-06-01"),
            data_cancelamento=pd.Timestamp("2024-01-01"),
        )
        resultado = aplicar_dominio(entrada, ledger)
        assert pd.isna(resultado["data_cancelamento"].iloc[0])

    def test_preserva_valores_dentro_do_dominio(self, ledger):
        resultado = aplicar_dominio(self._entrada_minima(), ledger)
        assert resultado["idade"].iloc[0] == 30.0
        assert resultado["valor_mensalidade"].iloc[0] == 100.0


# ---------------------------------------------------------------------------
# Imputacao
# ---------------------------------------------------------------------------


class TestImputacao:
    def test_imputa_mediana_e_nao_media(self, ledger):
        """
        A mediana e exigida por ser robusta a extremos. Com esta amostra
        assimetrica, media e mediana divergem o suficiente para distinguir as
        duas estrategias.
        """
        entrada = pd.DataFrame(
            {
                "frequencia_semanal": [1.0, 1.0, 1.0, 1.0, 7.0, np.nan],
                "idade": [30.0] * 6,
                "modalidade_principal": ["Musculacao"] * 6,
                "unidade": ["Centro"] * 6,
                "checkins_app_mes": [5.0] * 6,
                "usa_app": [True] * 6,
            }
        )
        resultado = imputar(entrada, ledger)
        observados = pd.Series([1.0, 1.0, 1.0, 1.0, 7.0])
        assert resultado["frequencia_semanal"].iloc[-1] == observados.median()
        assert resultado["frequencia_semanal"].iloc[-1] != observados.mean()

    def test_imputa_zero_em_contagem_de_checkins(self, ledger):
        """Ausencia de check-in possui significado conhecido: nenhum check-in."""
        entrada = pd.DataFrame(
            {
                "frequencia_semanal": [3.0] * 3,
                "idade": [30.0] * 3,
                "modalidade_principal": ["Musculacao"] * 3,
                "unidade": ["Centro"] * 3,
                "checkins_app_mes": [10.0, 20.0, np.nan],
                "usa_app": [True] * 3,
            }
        )
        resultado = imputar(entrada, ledger)
        assert resultado["checkins_app_mes"].iloc[-1] == 0

    def test_nao_restam_ausentes_apos_imputacao(self, base_analitica):
        """
        Apos o ETL, o unico campo legitimamente ausente e a data de
        cancelamento dos alunos ativos, cuja ausencia carrega significado.
        """
        ausentes = base_analitica.isna().sum()
        colunas_com_ausentes = set(ausentes[ausentes > 0].index)
        assert colunas_com_ausentes <= {"data_cancelamento"}


# ---------------------------------------------------------------------------
# Outliers
# ---------------------------------------------------------------------------


class TestOutliers:
    def test_detecta_extremo_evidente(self):
        serie = pd.Series([10, 11, 12, 11, 10, 12, 11, 10, 500])
        mascara, limites = detectar_outliers_iqr(serie)
        assert bool(mascara.iloc[-1]) is True
        assert int(mascara.sum()) == 1
        assert limites["limite_superior"] < 500

    def test_nao_sinaliza_ausentes(self):
        serie = pd.Series([10, 11, 12, np.nan, 11, 10])
        mascara, _ = detectar_outliers_iqr(serie)
        assert bool(mascara.isna().any()) is False
        assert int(mascara.sum()) == 0

    def test_amostra_insuficiente_nao_levanta_excecao(self):
        mascara, limites = detectar_outliers_iqr(pd.Series([1.0, 2.0]))
        assert int(mascara.sum()) == 0
        assert limites == {}

    def test_outliers_sao_sinalizados_e_nao_removidos(self, base_bruta):
        """
        Regressao: a remocao de extremos eliminaria os contratos de maior valor,
        que sustentam a analise de concentracao de receita.
        """
        ledger = QualityLedger()
        resultado = transformar(base_bruta.copy(), ledger)
        assert "outlier_qualquer" in resultado.columns
        assert ETL.outlier_estrategia == "flag"
        assert int(resultado["outlier_qualquer"].sum()) > 0, (
            "a base deve conter extremos detectaveis para sustentar a analise"
        )


# ---------------------------------------------------------------------------
# Atributos derivados
# ---------------------------------------------------------------------------


class TestAtributosDerivados:
    def test_tempo_de_vinculo_nunca_negativo(self, base_analitica):
        assert (base_analitica["dias_vinculo"] >= 0).all()

    def test_evasao_precoce_respeita_a_janela_do_tap(self, base_analitica):
        precoces = base_analitica.loc[base_analitica["evasao_precoce"]]
        assert (precoces["dias_vinculo"] <= BUSINESS.janela_evasao_critica_dias).all()
        assert precoces["evadiu"].all(), "evasao precoce exige evasao registrada"

    def test_status_coerente_com_indicador_de_evasao(self, base_analitica):
        assert (
            base_analitica.loc[base_analitica["evadiu"], "status"] == "Cancelado"
        ).all()
        assert (
            base_analitica.loc[~base_analitica["evadiu"], "status"] == "Ativo"
        ).all()

    def test_receita_acumulada_nao_negativa(self, base_analitica):
        assert (base_analitica["receita_acumulada"] >= 0).all()


# ---------------------------------------------------------------------------
# Contrato da base analitica
# ---------------------------------------------------------------------------


class TestContratoDaBaseAnalitica:
    def test_chave_primaria_unica(self, base_analitica):
        assert base_analitica["id_aluno"].duplicated().sum() == 0

    def test_categorias_dentro_do_dominio(self, base_analitica):
        assert set(base_analitica["plano"].unique()) <= set(BUSINESS.planos_validos)
        assert set(base_analitica["unidade"].unique()) <= set(BUSINESS.unidades_validas)

    def test_intervalos_numericos_respeitados(self, base_analitica):
        assert base_analitica["idade"].between(
            BUSINESS.idade_min, BUSINESS.idade_max
        ).all()
        assert base_analitica["frequencia_semanal"].between(
            BUSINESS.frequencia_min, BUSINESS.frequencia_max
        ).all()
        assert (base_analitica["valor_mensalidade"] > 0).all()

    def test_tipos_inteiros_restaurados(self, base_analitica):
        assert pd.api.types.is_integer_dtype(base_analitica["idade"])
        assert pd.api.types.is_integer_dtype(base_analitica["checkins_app_mes"])

    def test_perda_de_registros_dentro_do_tolerado(self, base_bruta):
        ledger = QualityLedger()
        transformar(base_bruta.copy(), ledger)
        assert ledger.taxa_perda <= ETL.limite_perda_registros

    def test_perda_excessiva_interrompe_o_pipeline(self):
        """
        Uma base majoritariamente invalida deve abortar a execucao, e nao
        produzir indicadores sobre o residuo sobrevivente.
        """
        n = 400
        entrada = pd.DataFrame(
            {
                "id_aluno": range(n),
                "data_matricula": ["2024-01-01"] * n,
                "data_cancelamento": [None] * n,
                # Mensalidade negativa e campo critico: sera anulada e descartada.
                "valor_mensalidade": [-100.0] * n,
                "plano": ["Mensal"] * n,
                "unidade": ["Centro"] * n,
                "modalidade_principal": ["Musculacao"] * n,
                "idade": [30] * n,
                "frequencia_semanal": [3.0] * n,
                "usa_app": ["True"] * n,
                "checkins_app_mes": [5] * n,
            }
        )
        with pytest.raises(DataLossError):
            transformar(entrada, QualityLedger())


# ---------------------------------------------------------------------------
# Trilha de auditoria
# ---------------------------------------------------------------------------


class TestTrilhaDeAuditoria:
    def test_todo_tratamento_declara_justificativa(self, base_bruta):
        ledger = QualityLedger()
        transformar(base_bruta.copy(), ledger)
        assert len(ledger.tratamentos) > 0
        for tratamento in ledger.tratamentos:
            assert tratamento.justificativa.strip(), (
                f"tratamento '{tratamento.regra}' sem justificativa declarada"
            )
            assert tratamento.acao.strip()

    def test_relatorio_serializavel(self, base_bruta):
        import json

        ledger = QualityLedger()
        transformar(base_bruta.copy(), ledger)
        json.dumps(ledger.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------


class TestIndicadores:
    def test_todo_kpi_declara_justificativa_e_objetivo(self):
        """
        Restricao central da entrega: nenhum indicador pode existir sem
        justificativa e sem vinculo a um objetivo do TAP.
        """
        for definicao in CATALOGO_KPI:
            assert definicao.justificativa.strip(), f"{definicao.codigo} sem justificativa"
            assert definicao.formula.strip(), f"{definicao.codigo} sem formula"
            assert definicao.objetivo_smart.startswith("OE-"), (
                f"{definicao.codigo} sem vinculo a objetivo SMART"
            )
            assert definicao.direcao_desejada in {"minimizar", "maximizar", "monitorar"}

    def test_codigos_de_kpi_sao_unicos(self):
        codigos = [d.codigo for d in CATALOGO_KPI]
        assert len(codigos) == len(set(codigos))

    def test_todos_os_kpis_calculam_sem_erro(self, base_analitica):
        relatorio = calcular_kpis(base_analitica)
        falhas = [r.codigo for r in relatorio.resultados if r.erro]
        assert not falhas, f"indicadores com falha: {falhas}"

    def test_percentuais_dentro_do_intervalo_valido(self, base_analitica):
        relatorio = calcular_kpis(base_analitica)
        for resultado in relatorio.resultados:
            if resultado.unidade == "%" and not np.isnan(resultado.valor):
                assert 0 <= resultado.valor <= 100, (
                    f"{resultado.codigo} fora do intervalo percentual: {resultado.valor}"
                )

    def test_base_vazia_nao_levanta_excecao(self, base_analitica):
        vazia = base_analitica.iloc[0:0]
        relatorio = calcular_kpis(vazia)
        assert len(relatorio.resultados) == len(CATALOGO_KPI)

    def test_carteira_de_risco_aplica_os_dois_criterios(self, base_analitica):
        ativos = base_analitica.loc[~base_analitica["evadiu"]]
        em_risco = ativos.loc[carteira_de_risco(ativos)]
        assert (~em_risco["usa_app"]).all()
        assert (
            em_risco["frequencia_semanal"] < BUSINESS.frequencia_alvo_semanal
        ).all()


# ---------------------------------------------------------------------------
# Estatistica
# ---------------------------------------------------------------------------


class TestEstatistica:
    def test_cohen_d_nulo_para_grupos_identicos(self):
        grupo = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(_cohen_d(grupo, grupo.copy())) < 1e-9

    def test_cohen_d_positivo_quando_primeiro_grupo_e_maior(self):
        assert _cohen_d(np.array([10.0, 11.0, 12.0]), np.array([1.0, 2.0, 3.0])) > 0

    def test_cohen_d_com_amostra_insuficiente_retorna_nan(self):
        assert np.isnan(_cohen_d(np.array([1.0]), np.array([2.0, 3.0])))

    def test_cramers_v_dentro_do_intervalo_unitario(self):
        v = _cramers_v(qui_quadrado=50.0, n=500, linhas=2, colunas=2)
        assert 0.0 <= v <= 1.0

    def test_detecta_colinearidade_declarada(self):
        matriz = pd.DataFrame(
            {"a": [1.0, 0.97, 0.10], "b": [0.97, 1.0, 0.12], "c": [0.10, 0.12, 1.0]},
            index=["a", "b", "c"],
        )
        achados = detectar_colinearidade(matriz, limite=0.90)
        assert len(achados) == 1
        assert {achados[0]["variavel_a"], achados[0]["variavel_b"]} == {"a", "b"}

    def test_normalidade_determina_o_metodo_de_referencia(self, base_analitica):
        """
        O teste de normalidade nao e decorativo: seu resultado deve estar
        refletido na implicacao metodologica declarada.
        """
        relatorio = executar_analise(base_analitica)
        assert relatorio.distribuicoes
        for distribuicao in relatorio.distribuicoes:
            if distribuicao.normal:
                assert "parametricos sao aplicaveis" in distribuicao.implicacao_metodologica
            else:
                assert "nao parametricos" in distribuicao.implicacao_metodologica

    def test_correlacoes_dentro_do_intervalo_valido(self, base_analitica):
        relatorio = executar_analise(base_analitica)
        for correlacao in relatorio.correlacoes:
            assert -1.0 <= correlacao.coeficiente <= 1.0
            assert 0.0 <= correlacao.p_valor <= 1.0

    def test_hipotese_central_do_projeto_se_sustenta(self, base_analitica):
        """
        Verifica que a associacao negativa entre frequencia e evasao, hipotese
        H1 do plano de analise, e detectada e significativa.
        """
        relatorio = executar_analise(base_analitica)
        alvo = [
            c
            for c in relatorio.correlacoes
            if c.metodo == "Ponto-bisserial" and c.variavel_y == "frequencia_semanal"
        ]
        assert alvo, "correlacao entre evasao e frequencia nao foi calculada"
        assert alvo[0].coeficiente < 0, "esperada associacao negativa"
        assert alvo[0].significativo


# ---------------------------------------------------------------------------
# Integracao
# ---------------------------------------------------------------------------


class TestIntegracao:
    def test_pipeline_executa_de_ponta_a_ponta(self, tmp_path):
        from src.pipeline import executar_pipeline

        resultado = executar_pipeline(gerar_figuras=False, persistir=False)

        assert len(resultado.base_analitica) > 0
        assert len(resultado.kpis.resultados) == len(CATALOGO_KPI)
        assert resultado.estatisticas.descritivas
        assert resultado.duracao_segundos > 0

        resumo = resultado.resumo()
        assert resumo["registros_processados"] > 0
        assert resumo["taxa_perda_pct"] <= ETL.limite_perda_registros * 100
