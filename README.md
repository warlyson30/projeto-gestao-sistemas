# projeto-gestao-sistemas

[![testes](https://github.com/warlyson30/projeto-gestao-sistemas/actions/workflows/tests.yml/badge.svg)](https://github.com/warlyson30/projeto-gestao-sistemas/actions/workflows/tests.yml)

Projeto em Gestão de Sistemas Computacionais. O repositório reúne as entregas
das quatro disciplinas do projeto, todas aplicadas ao mesmo estudo de caso.

## Estudo de caso

Academia Vértice Fit, empresa fictícia do ramo de musculação e treino
funcional. O sistema de gestão registra check-in, frequência e plano dos
alunos, além do estoque de suplementos e equipamentos.

Duas dores de negócio orientam as quatro entregas:

1. **Evasão de alunos.** A academia não identifica quais alunos estão prestes a
   cancelar o plano e perde receita recorrente sem tempo de reagir.
2. **Ineficiência operacional.** A alocação de horários e instrutores nos
   períodos de pico é inadequada, e o custo de reposição junto a fornecedores é
   elevado.

## Entregas

| Diretório | Disciplina | Contribuição para o estudo de caso |
|-----------|------------|------------------------------------|
| Não publicada | Gestão de Projetos | Termo de Abertura do Projeto, escopo e objetivos SMART |
| [`disciplina-2-analise-de-dados/`](disciplina-2-analise-de-dados) | Análise de Dados | Pipeline de ETL, indicadores, análise estatística e visualizações |
| Não publicada | Segurança da Informação | Mapeamento de riscos e adequação à LGPD |
| Não publicada | Pesquisa Operacional | Otimização da grade de horários e do custo de reposição |

Cada diretório é autocontido: código, dados, relatórios e instruções de
execução próprios, sem dependência entre disciplinas.

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

## Equipe

- Andrielly Campos da Silva
- Gustavo Prota da Silva Barbosa
- Henryque Gomes Moura Cunha
- Luana Mariana Lopes Bomfim
- Lucas Ferreira Mamede
- Warlyson Machado de Araujo

Os números de registro acadêmico constam nos documentos de entrega e não são
publicados aqui: são dado pessoal, e a própria Disciplina 3 do projeto trata da
adequação à LGPD.

## Licença

Distribuído sob a licença MIT. Ver [LICENSE](LICENSE).
