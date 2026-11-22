# DSL Financeira

Implementacao do interpretador descrito no artigo *"Especificacao e Projeto de
uma Linguagem de Dominio Especifico (DSL) para Modelagem e Simulacao Financeira
de Investimentos"* (Bruno Rafael Barbosa; Joao Pedro Magrin — FHO Araras).

## Estrutura do Projeto

O repositorio segue a organizacao padrao de pacotes Python (**PEP 621 / PyPA**):

```text
dsl_financeira/
├── pyproject.toml                   # Metadados do pacote, dependencias e entry points (PEP 621)
├── requirements.txt                 # Dependencias para instalacao rapida via pip
├── main.py                          # Entry point conveniente na raiz
├── README.md                        # Documentacao principal do repositorio
├── dsl_financeira/                  # Pacote principal do interpretador
│   ├── __init__.py                  # API publica do pacote (executar, analisar, classes)
│   ├── __main__.py                  # Suporte a execucao como modulo (python -m dsl_financeira)
│   ├── cli.py                       # Interface de linha de comando (CLI)
│   ├── gramatica.lark               # Gramatica formal (EBNF) para a biblioteca Lark
│   ├── parser.py                    # Front-End: Lexer e Parser LALR(1) / Earley
│   ├── semantico.py                 # AST Visitor de Analise Semantica
│   ├── tabela_simbolos.py           # Tabela de Simbolos e regras da tabela regressiva de IR
│   ├── interpretador.py             # AST Visitor de Execucao (calculos e graficos Matplotlib)
│   └── erros.py                     # Hierarquia de excecoes semanticas customizadas
├── exemplos/                        # Scripts de demonstracao na linguagem .dsl
│   ├── aposentadoria.dsl            # Cenario base do artigo IEEE
│   └── comparacao_cenarios.dsl      # Analise comparativa entre multiplos investimentos
├── testes/                          # Suite de testes automatizados (padrao unittest)
│   ├── __init__.py
│   └── teste_cenario.py             # Testes de arquitetura, simulacao, semantica e graficos
├── docs/                            # Documentacao tecnica e academica
│   ├── ANALISE_PROJETO.md           # Analise arquitetural e historico do projeto
│   ├── GUIA_ARTIGO_FINAL.md         # Guia e textos prontos para o artigo IEEE final
│   ├── PONTOS_EVOLUCAO.md           # Roadmap de evolucoes futuras da linguagem
│   └── Teoria_da_Computação_...pdf  # Artigo parcial de referencia
└── output/                          # Diretorio onde os graficos (.png) sao gerados (ignorado pelo Git)
```

## Pipeline

```text
Codigo Source (.dsl) -> Parser (Lark) -> AST -> Analise Semantica -> Execucao
```

1. **Front-End (Lexer e Parser)** — `dsl_financeira/parser.py` + `gramatica.lark`
   (biblioteca **Lark**, parser LALR(1); Earley tambem suportado).
2. **Analise Semantica e Tabela de Simbolos** — `semantico.py` + `tabela_simbolos.py`
   (heranca nativa de `lark.visitors.Interpreter`).
3. **Engine de Execucao (Interpretador)** — `interpretador.py` (AST Visitor via
   `lark.visitors.Interpreter`, juros compostos, deducoes fiscais fixas ou pela
   tabela regressiva de IR, e graficos individuais/comparativos salvos em `output/`).

## Gramatica (EBNF)

```text
programa          ::= (declaracao | comando)+
declaracao        ::= "INVESTIMENTO" STRING bloco_parametros "FIM"
bloco_parametros  ::= parametro+
parametro         ::= "VALOR_INICIAL" NUMBER
                    | "APORTE" NUMBER "POR" INT "MESES"
                    | "PERIODO" INT "MESES"
                    | "TAXA" NUMBER "PORCENTO" "AO_MES"
                    | "IMPOSTO" NUMBER "PORCENTO"
                    | "IMPOSTO" "REGRESSIVO"
comando           ::= "IMPRIMIR" "RESUMO" STRING
                    | "GERAR" "GRAFICO" STRING+
                    | "COMPARAR" "GRAFICO" STRING STRING+
```

## Tabela de Simbolos

| Campo | Simbolo | Descricao |
|---|---|---|
| Identificador | — | Nome do investimento (chave principal) |
| valor_inicial | P | Valor inicial |
| aporte | PMT | Aporte mensal |
| periodo | n | Periodo em meses |
| taxa | r | Taxa mensal (decimal) |
| imposto | t | Aliquota de imposto (decimal, fixa ou regressiva) |

### Erros semanticos

- `DeclaracaoDuplicadaError` — declaracao duplicada do mesmo investimento.
- `InvestimentoNaoDeclaradoError` — referencia a investimento nao declarado.
- `ValorForaDoDominioError` — valores numericos fora do dominio valido.
- `ParametroDuplicadoError` — parametro repetido ou conflitante no mesmo bloco `INVESTIMENTO`.
- `ParametroObrigatorioError` — ausencia de prazo definido (`PERIODO` ou `APORTE ... POR <n> MESES`).

## Instalacao

```bash
pip install -r requirements.txt
```

Ou instalando o pacote em modo editavel (PEP 621):

```bash
pip install -e .
```

## Uso

Via modulo Python (padrao de pacotes) ou via script na raiz:

```bash
python -m dsl_financeira exemplos/aposentadoria.dsl
python -m dsl_financeira exemplos/comparacao_cenarios.dsl
```

```bash
python main.py exemplos/aposentadoria.dsl
python main.py exemplos/comparacao_cenarios.dsl
```

Os graficos gerados pelos comandos `GERAR GRAFICO` e `COMPARAR GRAFICO` sao salvos automaticamente na pasta `output/`.

## Testes

Execucao com o runner padrao `unittest` do Python:

```bash
python -m unittest discover -s testes -p "teste_*.py" -v
```

Ou diretamente pelo modulo de testes:

```bash
python -m testes.teste_cenario
```

## Modelo de calculo

```text
FV_aportes          = PMT * ((1 + r)^n - 1) / r
FV_inicial          = P * (1 + r)^n
Total Investido     = P + PMT * n
Rendimento Bruto    = (FV_inicial + FV_aportes) - Total Investido
Imposto de Renda    = Rendimento Bruto * t
Valor Final Liquido = FV_inicial + FV_aportes - Imposto de Renda
```
