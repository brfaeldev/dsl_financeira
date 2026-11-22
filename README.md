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
│   ├── cli.py                       # Interface de linha de comando (CLI) e modo interativo (REPL)
│   ├── gramatica.lark               # Gramatica formal (EBNF) para a biblioteca Lark
│   ├── parser.py                    # Front-End: Lexer e Parser LALR(1) / Earley
│   ├── semantico.py                 # AST Visitor de Analise Semantica
│   ├── tabela_simbolos.py           # Tabela de Simbolos (investimentos, indices e regras de IR)
│   ├── interpretador.py             # AST Visitor de Execucao (calculos, graficos PNG/HTML, CSV/JSON)
│   └── erros.py                     # Hierarquia de excecoes semanticas customizadas
├── exemplos/                        # Scripts de demonstracao na linguagem .dsl
│   ├── aposentadoria.dsl            # Cenario base do artigo IEEE
│   ├── comparacao_cenarios.dsl      # Analise comparativa entre multiplos investimentos
│   └── planejamento_avancado.dsl    # Cenario completo (CDI, IPCA+, inflacao, safras, come-cotas, renda)
├── vscode-dsl-financeira/           # Extensao TextMate de Syntax Highlighting para VS Code
│   ├── package.json
│   ├── language-configuration.json
│   └── syntaxes/dsl.tmLanguage.json
├── testes/                          # Suite de testes automatizados (padrao unittest)
│   ├── __init__.py
│   └── teste_cenario.py             # 36 testes de arquitetura, simulacao, semantica, graficos e CLI/REPL
└── output/                          # Diretorio onde os graficos e relatorios sao gerados
```

## Pipeline

```text
Codigo Source (.dsl) -> Parser (Lark) -> AST -> Analise Semantica -> Execucao
```

1. **Front-End (Lexer e Parser)** — `dsl_financeira/parser.py` + `gramatica.lark`
   (biblioteca **Lark**, parser LALR(1); Earley tambem suportado).
2. **Analise Semantica e Tabela de Simbolos** — `semantico.py` + `tabela_simbolos.py`
   (heranca nativa de `lark.visitors.Interpreter`, conversao automatica de `AO_ANO` e `ANOS` para base mensal e validacao de indexadores e fluxos de caixa).
3. **Engine de Execucao (Interpretador)** — `interpretador.py` (AST Visitor via
   `lark.visitors.Interpreter`, juros compostos, deflacao real pela Equacao de Fisher,
   deducoes fiscais fixas, regressivas, por safra de aporte ou come-cotas, simulacao de
   renda passiva e geracao de graficos PNG/HTML, exportacoes CSV/JSON e relatorios Markdown).

## Gramatica (EBNF)

```text
programa          ::= (declaracao_indice | declaracao | comando)+
declaracao_indice ::= "INDICE" STRING NUMBER "PORCENTO" ("AO_MES" | "AO_ANO")
declaracao        ::= "INVESTIMENTO" STRING bloco_parametros "FIM"
bloco_parametros  ::= parametro+
parametro         ::= "VALOR_INICIAL" NUMBER
                    | "APORTE" NUMBER "POR" INT ("MESES" | "ANOS")
                    | "APORTE_EXTRA" NUMBER "NO_MES" INT
                    | "RESGATE" NUMBER "NO_MES" INT
                    | "PERIODO" INT ("MESES" | "ANOS")
                    | "TAXA" NUMBER "PORCENTO" ("AO_MES" | "AO_ANO")
                    | "TAXA" NUMBER "PORCENTO" "DO" STRING
                    | "TAXA" STRING "+" NUMBER "PORCENTO" ("AO_MES" | "AO_ANO")
                    | "TAXA" NUMBER "PORCENTO" ("AO_MES" | "AO_ANO") "+" STRING
                    | "TAXA_ADMINISTRACAO" NUMBER "PORCENTO" ("AO_MES" | "AO_ANO")
                    | "INFLACAO" NUMBER "PORCENTO" ("AO_MES" | "AO_ANO")
                    | "INFLACAO" STRING
                    | "IMPOSTO" NUMBER "PORCENTO"
                    | "IMPOSTO" "REGRESSIVO" ["POR_SAFRA"]
                    | "IMPOSTO" "COME_COTAS"
comando           ::= "IMPRIMIR" "RESUMO" STRING
                    | "GERAR" "GRAFICO" STRING+
                    | "GERAR" "GRAFICO_INTERATIVO" STRING+
                    | "COMPARAR" "GRAFICO" STRING STRING+
                    | "EXPORTAR" ("CSV" | "JSON") STRING+
                    | "GERAR" "RELATORIO" STRING+
                    | "SIMULAR" "RENDA" STRING "RETIRADA" NUMBER ("AO_MES" | "AO_ANO")
```

## Uso

Execucao de scripts `.dsl`:

```bash
python -m dsl_financeira exemplos/aposentadoria.dsl
python -m dsl_financeira exemplos/comparacao_cenarios.dsl
python -m dsl_financeira exemplos/planejamento_avancado.dsl
```

Modo interativo (REPL):

```bash
python -m dsl_financeira --repl
```

Playground Web visual (Streamlit):

```bash
pip install streamlit
streamlit run app.py
```

## Testes

Execucao com o runner padrao `unittest` do Python:

```bash
python -m unittest discover -s testes -p "teste_*.py" -v
```
