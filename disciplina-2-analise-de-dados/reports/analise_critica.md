# Analise Critica (Secao 2.4)

**Projeto:** Academia Vertice Fit — Disciplina 2, Analise de Dados
**Base analisada:** 1.478 alunos validos, extraidos de 1.545 registros brutos
**Periodo de referencia:** janeiro de 2024 a dezembro de 2025

---

## Pergunta obrigatoria

> Baseado nas correlacoes estatisticas, nos outliers encontrados e no principal
> KPI calculado, qual e o maior gargalo operacional da empresa escolhida?
> Explique como esses dados numericos justificam as metas e o escopo definidos
> no Termo de Abertura do Projeto (TAP), na Disciplina 1.

---

## Resposta

O maior gargalo operacional da Academia Vertice Fit nao e a captacao de novos
alunos, e sim a incapacidade de converter matricula em permanencia durante o
primeiro trimestre de contrato. O principal indicador calculado, a taxa de
evasao da carteira (KPI-01), atingiu 27,81%, e sua decomposicao revela onde o
problema se concentra: 28,95% de todos os cancelamentos ocorrem dentro dos
primeiros sessenta dias (KPI-02), e a permanencia media do aluno que evade e de
apenas 3,59 meses (KPI-07). A analise estatistica identificou a causa
comportamental dessa perda. A correlacao ponto-bisserial entre evasao e
frequencia semanal foi de -0,347 (p = 5,7 x 10⁻⁴³), e a comparacao entre os
dois grupos pelo teste de Mann-Whitney confirmou diferenca com tamanho de
efeito grande (d de Cohen = -0,82): o aluno retido comparece 3,78 vezes por
semana, contra 2,60 do aluno que cancela. O mesmo padrao aparece na dimensao
digital, com risco relativo de 2,44, ja que a evasao entre nao aderentes ao
aplicativo alcanca 47,40% contra 19,42% dos aderentes (qui-quadrado
p = 7,7 x 10⁻²⁸, V de Cramer = 0,28). O segmento de engajamento sintetiza os
dois fatores e apresenta a associacao mais forte de toda a analise
(V de Cramer = 0,37): a evasao varia de 12,89% no segmento de alto engajamento
a 56,58% no de baixo engajamento. Cabe registrar um achado negativo relevante:
a unidade de matricula nao apresentou associacao detectavel com a evasao
(p = 0,505), o que descarta a hipotese de causa estrutural ou de infraestrutura
fisica e reforca a natureza comportamental do gargalo.

A analise de dispersao e de outliers acrescenta a dimensao financeira do
problema e altera a prioridade da acao. O coeficiente de variacao da receita
acumulada por aluno e de 90,8%, indicando processo altamente instavel, e o
criterio de Tukey sinalizou 68 registros extremos, dos quais 42 correspondem a
contratos com acompanhamento personalizado. Esses 42 alunos, que representam
2,8% da carteira, respondem por 10,8% de toda a receita acumulada; de forma
mais ampla, os 20% maiores contratos concentram 46,88% do faturamento
(KPI-12). Como o valor da mensalidade nao apresentou associacao com a evasao
(r = -0,008, p = 0,750), o contrato de alto valor cancela na mesma proporcao
que o contrato padrao, porem com impacto financeiro varias vezes superior.
Esses extremos foram deliberadamente sinalizados e preservados na base, e nao
removidos: descarta-los teria eliminado justamente o segmento que sustenta a
concentracao de receita e distorcido para baixo toda a estimativa de perda. O
conjunto desses numeros justifica diretamente as metas e o escopo definidos no
TAP. A meta de reduzir o churn em dez pontos percentuais (OE-01) e realista
porque a diferenca observada entre segmentos, de 43,69 pontos, e muito superior
a ela, evidenciando margem de manobra. O recorte de carteira de risco (OE-02)
deixou de ser arbitrario e passou a ter criterio verificavel: os 122 alunos
ativos que combinam ausencia de adesao digital e frequencia inferior a tres
dias semanais representam 11,43% da base e R$ 14.426,65 de receita mensal em
risco (KPI-08 e KPI-09), montante que estabelece o teto economico defensavel
para o investimento em retencao. A meta de elevar a adesao ao aplicativo para
80% (OE-03) e sustentada por ser esta a unica variavel do modelo diretamente
influenciavel pela empresa, ao contrario da frequencia, que depende da
disponibilidade do aluno. Por fim, a taxa de subutilizacao de 31,30% (KPI-10)
quantifica a demanda reprimida que alimenta o modelo de otimizacao da grade de
horarios da Disciplina 4, assegurando continuidade metodologica entre as
etapas do projeto.

---

## Ressalvas metodologicas

A analise apresentada e observacional e transversal. Ela estabelece associacao
estatistica, nao causalidade, e permanece sujeita a causalidade reversa: o
aluno pode reduzir a frequencia por ja ter decidido cancelar, em vez de
cancelar por frequentar pouco. A confirmacao causal exigiria desenho
experimental, com grupo de controle, o que se recomenda como escopo de etapa
posterior.

Duas restricoes tecnicas foram identificadas e tratadas explicitamente durante
a analise. A primeira e a colinearidade quase perfeita entre tempo de vinculo e
receita acumulada (Spearman = 0,97), detectada automaticamente pelo pipeline:
as duas variaveis carregam essencialmente a mesma informacao e nao devem ser
tratadas como evidencias independentes. A segunda e a censura a direita na
analise de coortes, corrigida pela adocao de janela fixa de observacao de
noventa dias e pela exclusao das coortes que ainda nao a completaram. Sem essa
correcao, as coortes recentes exibiriam evasao artificialmente baixa apenas por
ainda nao terem tido tempo de evadir, e o grafico sugeriria uma melhoria
inexistente.

Por fim, todas as seis variaveis continuas analisadas rejeitaram a hipotese de
normalidade. Por essa razao, os coeficientes de Spearman e os testes de
Mann-Whitney foram adotados como resultado de referencia, e os testes
parametricos equivalentes permanecem reportados apenas para comparacao.
