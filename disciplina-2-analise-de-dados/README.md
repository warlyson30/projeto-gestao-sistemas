# Vertice Fit Analytics

Pipeline analitico da Academia Vertice Fit. Transforma dados brutos do sistema
de gestao em indicadores de negocio, evidencia estatistica e artefatos visuais
que sustentam as decisoes tomadas no Termo de Abertura do Projeto.

Disciplina 2 do Projeto em Gestao de Sistemas Computacionais.

---

## Problema de negocio

A academia perde parte relevante da carteira nos primeiros meses de contrato,
sem instrumento para antecipar quais alunos cancelarao. O projeto responde a
essa lacuna produzindo, a partir dos dados operacionais, a identificacao da
carteira de risco e a quantificacao financeira da exposicao correspondente.

Objetivos SMART declarados no TAP e rastreados por este pipeline:

| Codigo | Objetivo | Meta |
|--------|----------|------|
| OE-01 | Reduzir a evasao por meio de acoes de retencao orientadas por dados | Reduzir o churn mensal em 10 pontos percentuais em 3 meses |
| OE-02 | Identificar antecipadamente a parcela de maior propensao ao cancelamento | Classificar 20% da base como carteira de risco em 3 meses |
| OE-03 | Elevar o engajamento digital no aplicativo proprio | Elevar a adesao ao aplicativo para 80% da base ativa em 6 meses |
| OE-04 | Otimizar a ocupacao da grade e a alocacao de instrutores | Reduzir a ociosidade da grade em 15% em 6 meses |

---

## Arquitetura

```
vertice_fit_analytics/
├── config/
│   └── settings.py              Configuracao central: regras de negocio,
│                                objetivos SMART, parametros de ETL,
│                                estatistica e visualizacao
├── src/
│   ├── logger.py                Logging estruturado (console e arquivo)
│   ├── data_generation.py       Gerador da base bruta sintetica
│   ├── pipeline.py              Orquestrador das quatro etapas
│   ├── etl/
│   │   ├── extract.py           Leitura tipada e contrato de schema
│   │   ├── validate.py          Trilha de auditoria, perfilagem e IQR
│   │   ├── transform.py         Sete etapas encadeadas de limpeza
│   │   └── load.py              Persistencia em Parquet e CSV
│   ├── kpi/
│   │   ├── definitions.py       Catalogo de 12 indicadores justificados
│   │   └── engine.py            Motor de calculo e segmentacoes
│   ├── stats_engine/
│   │   ├── analysis.py          Descritiva, distribuicao, correlacao, efeito
│   │   └── plan.py              Plano de analise com hipoteses declaradas
│   └── viz/
│       └── charts.py            Oito graficos com tema corporativo unico
├── data/
│   ├── raw/                     Base bruta, como extraida da origem
│   ├── interim/                 Base analitica em Parquet (tipos preservados)
│   └── processed/               Base analitica em CSV (interoperabilidade)
├── reports/
│   ├── figures/                 Artefatos graficos
│   ├── data_quality_report.json Trilha completa de tratamentos do ETL
│   ├── kpi_report.json          Indicadores com metadados e justificativas
│   └── statistical_report.json  Resultados dos testes de hipotese
├── tests/                       Suite com 49 testes automatizados
├── notebooks/                   Versao executavel no Google Colab
├── main.py                      Ponto de entrada de linha de comando
└── requirements.txt
```

O acoplamento entre camadas e unidirecional. Os modulos de ETL, indicadores,
estatistica e visualizacao nao se importam entre si: toda a coordenacao ocorre
em `src/pipeline.py`. Substituir a fonte de dados, acrescentar um indicador ou
trocar a biblioteca grafica nao exige alteracao nas demais camadas.

---

## Execucao

```bash
pip install -r requirements.txt

python main.py                    # execucao padrao
python main.py --regenerar        # regenera a base bruta antes de executar
python main.py --sem-figuras      # suprime a etapa de visualizacao
python main.py --sem-persistencia # executa em memoria, sem gravar artefatos

pytest                            # suite de testes
```

O codigo de saida e zero em caso de sucesso e um em caso de falha estrutural,
permitindo encadeamento em agendadores sem inspecao do texto de log.

Para execucao no Google Colab, utilize `notebooks/D2_Analise_Dados.ipynb`.

---

## Decisoes tecnicas

### A ordem do ETL e significativa

As sete etapas de transformacao nao sao operacoes independentes. Inverter
qualquer uma delas altera o resultado numerico:

1. **Normalizacao** precede a deduplicacao. Sem padronizar `"mensal"`,
   `"MENSAL"` e `" Mensal "` para uma unica forma, a deduplicacao trataria o
   mesmo registro como tres distintos.
2. **Deduplicacao** precede a imputacao. Registros replicados enviesariam a
   mediana e a moda usadas no preenchimento de ausentes.
3. **Validacao de dominio** precede a imputacao. Uma idade registrada como 999
   contaminaria a mediana se fosse anulada apenas depois.
4. **Descarte de irrecuperaveis** ocorre antes da imputacao dos demais campos.
5. **Imputacao** com estrategia declarada por coluna.
6. **Deteccao de outliers**, em duas passagens de finalidade distinta.
7. **Engenharia de atributos**, que depende de todas as anteriores.

### Trilha de auditoria obrigatoria

Todo tratamento aplicado registra no `QualityLedger` a regra executada, a
coluna afetada, o volume de registros impactados e a justificativa tecnica da
decisao. Um pipeline que altera dados sem deixar rastro nao e auditavel: se um
indicador apresentar valor inesperado, o ledger permite identificar qual regra
o produziu sem reexecutar o processo em modo de depuracao.

O pipeline aborta automaticamente se a limpeza descartar mais de 20% dos
registros. Perda dessa magnitude indica defeito sistemico na origem, e
prosseguir produziria indicadores nao representativos.

### Outliers sao sinalizados, nunca removidos

A deteccao usa o criterio de Tukey (amplitude interquartil), preferido ao
z-score por nao pressupor normalidade e por seus limites nao serem
influenciados pelos proprios extremos que se pretende identificar.

Os extremos sao marcados em colunas dedicadas e preservados na base. Em uma
academia, o aluno de frequencia ou ticket extremo e o ativo comercial mais
valioso da carteira: exclui-lo suprimiria justamente a evidencia que sustenta a
analise de concentracao de receita.

A deteccao ocorre em duas passagens com lentes distintas. Sobre as variaveis de
origem, o extremo levanta suspeita de defeito de captura. Sobre as variaveis
derivadas, o extremo representa comportamento comercial real e relevante.

### Nenhum indicador e arbitrario

O catalogo de KPIs adota o padrao de registro: a definicao do indicador e o seu
calculo residem na mesma estrutura, de modo que e estruturalmente impossivel
acrescentar uma metrica ao relatorio sem declarar simultaneamente sua formula,
sua unidade, a direcao desejada, o objetivo SMART que ela mede e a justificativa
de sua existencia. A restricao impede a proliferacao de metricas sem proposito,
problema recorrente em paineis gerenciais.

### A normalidade determina o metodo estatistico

O teste de normalidade nao e executado como formalidade. Seu resultado
seleciona a familia de testes aplicada em seguida: sob normalidade, Pearson e
o t de Student; caso contrario, Spearman e Mann-Whitney sao reportados como
resultado de referencia, e os testes parametricos permanecem apenas para
comparacao. Reportar Pearson sobre variaveis comprovadamente nao normais seria
erro metodologico, ainda que o numero produzido parecesse plausivel.

A escolha do teste de normalidade tambem depende do tamanho da amostra.
Shapiro-Wilk tem maior poder em amostras pequenas, porem rejeita a hipotese
nula diante de desvios triviais quando a amostra e grande; acima de 5000
observacoes o pipeline emprega D'Agostino-Pearson.

### Todo valor-p acompanha tamanho de efeito

Com amostras da ordem de milhares de registros, diferencas irrelevantes para o
negocio atingem significancia estatistica com facilidade. Por isso todo teste
reporta tambem a magnitude do efeito: d de Cohen para comparacao de grupos,
V de Cramer para associacao categorica. A significancia isolada nao distingue
diferenca relevante de diferenca trivial.

### Hipoteses sao declaradas antes da execucao

O plano de analise em `src/stats_engine/plan.py` fixa as cinco hipoteses
testadas antes de qualquer execucao. Isso evita a pratica de percorrer todas as
combinacoes possiveis de variaveis e reportar apenas as significativas,
procedimento que inflaciona artificialmente a taxa de falsos positivos.

### Colinearidade e detectada automaticamente

Pares de variaveis com correlacao acima de 0.90 sao sinalizados com alerta em
log e registrados no relatorio estatistico. A deteccao e automatizada, e nao
deixada a inspecao visual do mapa de calor, porque a colinearidade tem
consequencia concreta: duas variaveis quase perfeitamente correlacionadas
carregam a mesma informacao, e trata-las como evidencias independentes
constitui dupla contagem.

### A analise de coorte controla a censura a direita

A taxa de evasao por coorte e medida dentro de uma janela fixa de 90 dias, e
coortes que ainda nao completaram a janela sao excluidas. Sem esse controle, as
coortes recentes exibiriam evasao artificialmente baixa apenas por ainda nao
terem tido tempo de evadir, e o grafico sugeriria uma melhoria que nao ocorreu.

### Base sintetica com defeitos deliberados

A base bruta e gerada com imperfeicoes injetadas de forma controlada: valores
ausentes, duplicatas, categorias com digitacao livre, valores fora de dominio e
datas em formatos mistos. Cada defeito injetado possui tratamento
correspondente no ETL, tornando o pipeline auditavel de ponta a ponta.

A geracao e determinística: a mesma semente reproduz exatamente a mesma base, o
que garante a reprodutibilidade dos resultados apresentados na documentacao.

---

## Cobertura dos requisitos da disciplina

| Requisito | Implementacao |
|-----------|---------------|
| 2.1 Tratamento de dados (ETL) | `src/etl/`, com trilha de auditoria em `reports/data_quality_report.json` |
| 2.1 Justificativa dos KPIs | `src/kpi/definitions.py`, 12 indicadores vinculados a objetivos SMART |
| 2.2 Descritiva basica | Media, mediana, desvio padrao e coeficiente de variacao para 6 variaveis |
| 2.2 Distribuicao | Assimetria, curtose e teste formal de normalidade |
| 2.2 Correlacao | Pearson, Spearman, ponto-bisserial, Mann-Whitney e qui-quadrado |
| 2.3 Visualizacao | 8 graficos selecionados, com criterio de selecao declarado |
| 2.4 Analise critica | `reports/analise_critica.md` |

Dos dez tipos de grafico previstos no guia, oito foram selecionados e dois
descartados com justificativa registrada em `JUSTIFICATIVA_SELECAO`, no modulo
de visualizacao. A selecao e deliberada: um painel que reproduz todos os tipos
disponiveis demonstra dominio da biblioteca, nao dominio do problema.

---

## Compatibilidade

O codigo opera em pandas 2.x e 3.x sem alteracao, evitando APIs depreciadas
como o parametro `inplace` encadeado e a atribuicao sobre fatias. A extracao de
resultados do SciPy normaliza tanto o retorno em tupla das versoes anteriores
quanto os objetos com atributos `statistic` e `pvalue` das versoes recentes.

A ausencia de `pyarrow` nao interrompe a execucao: a camada intermediaria
degrada para CSV com aviso registrado em log.
