# projeto-gestao-sistemas

[![testes](https://github.com/warlyson30/projeto-gestao-sistemas/actions/workflows/tests.yml/badge.svg)](https://github.com/warlyson30/projeto-gestao-sistemas/actions/workflows/tests.yml)

Repositório oficial do projeto de Análise e Gestão de Sistemas para otimização
de processos operacionais.

Projeto em Gestão de Sistemas Computacionais.

## Integrantes

| Nome completo | RA |
|---------------|----|
| Lucas Ferreira Mamede | |
| Luana Mariana Lopes Bomfim | |
| Warlyson Machado de Araujo | |
| Gustavo Prota da Silva Barbosa | |
| Andrielly Campos da Silva | |
| Henryque Gomes Moura Cunha | |

## Empresa

**Nome:** Academia Vértice Fit (empresa fictícia).

**Ramo de atuação:** academia de musculação e funcional, com sistema de gestão
que registra check-in, frequência e plano dos alunos, além de controle de
estoque de suplementos e equipamentos.

## O problema

A Academia Vértice Fit enfrenta duas dores centrais de negócio que o projeto
pretende resolver ao longo das quatro disciplinas:

1. **Alta evasão de alunos (churn).** A academia não consegue prever quais
   alunos estão prestes a cancelar o plano, perdendo receita recorrente sem
   tempo de agir.
2. **Ineficiência operacional.** Má alocação de horários e instrutores nos
   períodos de pico, e custos elevados na reposição de suplementos e
   equipamentos junto a fornecedores.

## Abordagem por disciplina

O grupo utilizará:

| Disciplina | Papel no projeto | Entrega neste repositório |
|------------|------------------|---------------------------|
| Gestão de Projetos | Planejar e documentar formalmente a iniciativa | Não publicada |
| Análise de Dados (Python) | Identificar os fatores ligados ao churn a partir de dados de frequência e uso dos alunos | [`disciplina-2-analise-de-dados/`](disciplina-2-analise-de-dados) |
| Segurança da Informação | Mapear riscos e adequar o tratamento de dados pessoais e de saúde à LGPD | Não publicada |
| Pesquisa Operacional | Maximizar o lucro na alocação de horários e instrutores e minimizar o custo de reposição junto aos fornecedores | Não publicada |

Cada diretório de entrega é autocontido: código, dados, relatórios e instruções
de execução próprios, sem dependência entre disciplinas.

## Disciplina 2: Análise de Dados

Pipeline analítico em Python que transforma a extração bruta do sistema de
gestão em indicadores de negócio, evidência estatística e artefatos visuais,
com trilha de auditoria de cada tratamento aplicado aos dados. Documentação
completa em
[`disciplina-2-analise-de-dados/README.md`](disciplina-2-analise-de-dados/README.md).

Execução local:

```bash
cd disciplina-2-analise-de-dados
pip install -r requirements.txt
python main.py
```

Execução no Google Colab, sem instalação local e sem envio manual de arquivos.
A primeira célula do notebook obtém o repositório e prepara o ambiente:

[Abrir `D2_Analise_Dados.ipynb` no Colab](https://colab.research.google.com/github/warlyson30/projeto-gestao-sistemas/blob/main/disciplina-2-analise-de-dados/notebooks/D2_Analise_Dados.ipynb)

## Licença

Distribuído sob a licença MIT. Ver [LICENSE](LICENSE).
