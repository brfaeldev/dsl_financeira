# DSL Financeira

Implementacao do interpretador descrito no artigo *"Especificacao, Implementacao e Validacao de uma Linguagem de Dominio Especifico (DSL) para Modelagem e Simulacao Financeira de Investimentos"* (FHO | Fundacao Herminio Ometto — Araras/SP).

## 👥 Identificação

- **Bruno Rafael Barbosa** — RA: 112944
- **João Pedro Magrin** — RA: 113164

## Estrutura do Projeto

O repositorio segue a organizacao padrao de pacotes Python (**PEP 621 / PyPA**):

```text
dsl_financeira/
├── pyproject.toml                   # Metadados do pacote, dependencias e entry points (PEP 621)
├── requirements.txt                 # Dependencias para instalacao rapida via pip
├── main.py                          # Entry point conveniente na raiz (CLI / REPL)
├── app.py                           # Entry point conveniente na raiz (Playground Web Streamlit)
├── README.md                        # Documentacao principal do repositorio
├── dsl_financeira/                  # Pacote principal do interpretador
│   ├── __init__.py                  # API publica do pacote (executar, analisar, classes)
│   ├── __main__.py                  # Suporte a execucao como modulo (python -m dsl_financeira)
│   ├── cli.py                       # Interface de linha de comando (CLI) e modo interativo (REPL)
│   ├── playground.py                # Servicos e componentes visuais do Playground Web em Streamlit
│   ├── gramatica.lark               # Gramatica formal (EBNF) para a biblioteca Lark
│   ├── parser.py                    # Front-End: Lexer e Parser LALR(1) / Earley
│   ├── semantico.py                 # AST Visitor de Analise Semantica
│   ├── tabela_simbolos.py           # Tabela de Simbolos (investimentos, indices e regras de IR)
│   ├── interpretador.py             # AST Visitor de Execucao (orquestrador dos comandos da AST)
│   ├── motor.py                     # Motor matematico, financeiro e tributario (safras, IR, usufruto)
│   ├── graficos.py                  # Renderizacao grafica estatica (PNG) e interativa (HTML Plotly)
│   ├── exportacao.py                # Exportadores CSV/JSON, relatorios Markdown e formatacao
│   └── erros.py                     # Hierarquia de excecoes semanticas customizadas
├── docs/                            # Documentacao e artigo do projeto
│   └── Teoria_da_Computação_e_Compiladores.pdf  # Artigo IEEE final da DSL Financeira
├── exemplos/                        # Scripts de demonstracao na linguagem .dsl
│   ├── aposentadoria.dsl            # Cenario base do artigo IEEE
│   ├── comparacao_cenarios.dsl      # Analise comparativa entre multiplos investimentos
│   ├── planejamento_avancado.dsl    # Cenario completo (CDI, IPCA+, inflacao, safras, come-cotas, renda)
│   └── referencia_completa.dsl      # Template de referencia com todas as construcoes da linguagem
├── vscode-dsl-financeira/           # Extensao TextMate de Syntax Highlighting para VS Code
│   ├── package.json
│   ├── language-configuration.json
│   └── syntaxes/dsl.tmLanguage.json
├── testes/                          # Suite de testes automatizados modulares (padrao unittest)
│   ├── __init__.py
│   ├── teste_arquitetura.py         # Testes de arquitetura Visitor, cache e parser LALR(1)/Earley
│   ├── teste_semantico.py           # Testes de validacao semantica, Tabela de Simbolos e erros
│   ├── teste_motor.py               # Testes matematicos, financeiros, tributarios e de usufruto
│   ├── teste_saidas.py              # Testes de graficos PNG/HTML, exportacoes CSV/JSON e relatorio
│   └── teste_cli.py                 # Testes de CLI, REPL, gramatica VS Code e Playground
└── output/                          # Diretorio onde os graficos e relatorios sao gerados
```

## Pipeline

```text
Codigo Source (.dsl) -> Parser (Lark) -> AST -> Analise Semantica -> Execucao
```

1. **Front-End (Lexer e Parser)** — `dsl_financeira/parser.py` + `gramatica.lark`
   (biblioteca **Lark**, parser LALR(1) com cache em memoria; algoritmo Earley tambem suportado).
2. **Analise Semantica e Tabela de Simbolos** — `semantico.py` + `tabela_simbolos.py` + `erros.py`
   (heranca nativa de `lark.visitors.Interpreter`, conversao automatica de `AO_ANO` e `ANOS` para base mensal, validacao de limites de dominio/overflow, indexadores e viabilidade de saldo em resgates).
3. **Engine de Execucao e Modulos Especializados** — `interpretador.py` (orquestrador AST Visitor via `lark.visitors.Interpreter`) + `motor.py` (juros compostos, deflacao real pela Equacao de Fisher, deducoes fiscais fixas, regressivas, por safra de aporte ou come-cotas e simulacao de renda passiva/usufruto) + `graficos.py` (graficos PNG via Matplotlib e HTML interativo via Plotly) + `exportacao.py` (CSV, JSON e relatorios executivos em Markdown).
4. **Interfaces de Usuario** — `cli.py` (execucao de scripts `.dsl` via terminal e modo interativo REPL), `playground.py` / `app.py` (Playground Web e Inspetor de Compilador em Streamlit) e `vscode-dsl-financeira/` (extensao TextMate de realce de sintaxe para VS Code).

> Para a especificacao formal completa, fundamentacao matematica e validacao experimental, consulte [docs/Teoria_da_Computação_e_Compiladores.pdf](docs/Teoria_da_Computação_e_Compiladores.pdf) e o script modelo [exemplos/referencia_completa.dsl](exemplos/referencia_completa.dsl).

## Gramatica (EBNF)

```text
programa         ::= (decl_indice | declaracao | comando)+
decl_indice      ::= "INDICE" STRING numero "PORCENTO" UNIDADE_TAXA
declaracao       ::= "INVESTIMENTO" STRING bloco_parametros "FIM"
bloco_parametros ::= parametro+
parametro        ::= "VALOR_INICIAL" numero
                   | "APORTE" numero "POR" INT UNIDADE_PERIODO
                   | "APORTE_EXTRA" numero "NO_MES" INT
                   | "RESGATE" numero "NO_MES" INT
                   | "PERIODO" INT UNIDADE_PERIODO
                   | "TAXA" numero "PORCENTO" UNIDADE_TAXA
                   | "TAXA" numero "PORCENTO" "DO" STRING
                   | "TAXA" STRING "+" numero "PORCENTO" UNIDADE_TAXA
                   | "TAXA" numero "PORCENTO" UNIDADE_TAXA "+" STRING
                   | "TAXA_ADMINISTRACAO" numero "PORCENTO" UNIDADE_TAXA
                   | "INFLACAO" numero "PORCENTO" UNIDADE_TAXA
                   | "INFLACAO" STRING
                   | "IMPOSTO" numero "PORCENTO"
                   | "IMPOSTO" "REGRESSIVO" ["POR_SAFRA"]
                   | "IMPOSTO" "COME_COTAS"
comando          ::= "IMPRIMIR" "RESUMO" STRING
                   | "GERAR" "GRAFICO" STRING+
                   | "GERAR" "GRAFICO_INTERATIVO" STRING+
                   | "COMPARAR" "GRAFICO" STRING STRING+
                   | "EXPORTAR" ("CSV" | "JSON") STRING+
                   | "GERAR" "RELATORIO" STRING+
                   | "SIMULAR" "RENDA" STRING "RETIRADA" numero UNIDADE_TAXA
numero           ::= NUMBER | INT
```

## Instalação e Uso

Instalacao das dependencias:

```bash
pip install -r requirements.txt
```

Execucao de scripts `.dsl` via CLI:

```bash
python -m dsl_financeira exemplos/aposentadoria.dsl
python -m dsl_financeira exemplos/comparacao_cenarios.dsl
python -m dsl_financeira exemplos/planejamento_avancado.dsl
python -m dsl_financeira exemplos/referencia_completa.dsl

# Opcional: definir diretorio customizado para os artefatos gerados (-o)
python main.py exemplos/planejamento_avancado.dsl -o output
```

Modo interativo (REPL):

```bash
python -m dsl_financeira --repl
```

Playground Web visual (Streamlit):

```bash
streamlit run app.py
```

## Testes

Execucao da suite modular de **38 testes automatizados** com o runner padrao `unittest` do Python:

```bash
python -m unittest discover -s testes -p "teste_*.py" -v
```
