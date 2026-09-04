# projeto-gestao-sistemas
Repositório oficial do projeto de Análise e Gestão de Sistemas para otimização de processos operacionais.

Projeto em Gestão de Sistemas Computacionais


Integrantes:
Nome completo -	RA

[Lucas Ferreira Mamede]	[Ra]

[Luana Mariana Lopes Bomfim]	[Ra]

[Warlyson Machado de Araujo]	[Ra]

[Gustavo Prota da Silva Barbosa]	[Ra]

[Andrielly Campos da Silva]	[Ra]

[Henryque Gomes Moura Cunha]	[Ra]



Empresa
- Nome: Academia Vértice Fit (empresa fictícia)
  

Ramo de Atuação
- Academia de musculação e funcional, com sistema de gestão que registra check-in, frequência e plano dos alunos, além de controle de estoque de suplementos e equipamentos.
  

O Problema:

A Academia Vértice Fit enfrenta duas dores centrais de negócio que o projeto pretende resolver ao longo das 4 disciplinas:

Alta evasão de alunos (churn): a academia não consegue prever quais alunos estão prestes a cancelar o plano, perdendo receita recorrente sem tempo de agir.
Ineficiência operacional: má alocação de horários/instrutores nos períodos de pico e custos elevados na reposição de suplementos e equipamentos junto a fornecedores.


O grupo utilizará:

Gestão de Projetos para planejar e documentar formalmente a iniciativa;
Análise de Dados (Python) para identificar os fatores ligados ao churn a partir de dados de frequência e uso dos alunos;
Segurança da Informação para mapear riscos e adequar o tratamento de dados pessoais e de saúde à LGPD;
Pesquisa Operacional para maximizar o lucro na alocação de horários/instrutores e minimizar o custo de reposição junto aos fornecedores.
Repositório

Link deste repositório : [https://github.com/warlyson30/projeto-gestao-sistemas/tree/main]


---

## Estrutura do repositório

O repositório reúne as entregas das quatro disciplinas do projeto. Cada
disciplina ocupa um diretório próprio, com código, dados e relatórios
autocontidos.

| Diretório | Disciplina | Conteúdo |
|-----------|-----------|----------|
| `disciplina-2-analise-de-dados/` | Análise de Dados | Pipeline de ETL, catálogo de indicadores, análise estatística e visualizações da Academia Vértice Fit |

### Disciplina 2 — Análise de Dados

Pipeline analítico completo em Python, com trilha de auditoria de cada
tratamento aplicado aos dados. Documentação detalhada em
[`disciplina-2-analise-de-dados/README.md`](disciplina-2-analise-de-dados/README.md).

Execução local:

```bash
cd disciplina-2-analise-de-dados
pip install -r requirements.txt
python main.py
```

Execução no Google Colab: abra
`disciplina-2-analise-de-dados/notebooks/D2_Analise_Dados.ipynb`. A primeira
célula obtém o repositório e prepara o ambiente sozinha — não é necessário
enviar arquivos manualmente.
