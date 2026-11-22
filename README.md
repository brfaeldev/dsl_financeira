# DSL Financeira

Implementacao do interpretador descrito no artigo *"Especificacao e Projeto de
uma Linguagem de Dominio Especifico (DSL) para Modelagem e Simulacao Financeira
de Investimentos"* (Bruno Rafael Barbosa; Joao Pedro Magrin — FHO Araras).

## Pipeline

```
Codigo Source -> Parser -> AST -> Execucao
```

1. **Front-End (Lexer e Parser)** — `dsl_financeira/parser.py` + `gramatica.lark`
   (biblioteca **Lark**, parser LALR(1); Earley tambem suportado).
2. **Analise Semantica e Tabela de Simbolos** — `semantico.py` + `tabela_simbolos.py`
   (heranca nativa de `lark.visitors.Interpreter`).
3. **Engine de Execucao (Interpretador)** — `interpretador.py` (AST Visitor via
   `lark.visitors.Interpreter`, juros compostos, deducoes fiscais fixas ou pela
   tabela regressiva de IR, e graficos individuais/comparativos com **Matplotlib**).

## Gramatica (EBNF)

```
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

## Uso

```bash
python main.py exemplos/aposentadoria.dsl
python main.py exemplos/comparacao_cenarios.dsl
```

## Testes

```bash
python -m testes.teste_cenario
```

## Modelo de calculo

```
FV_aportes = PMT * ((1 + r)^n - 1) / r
FV_inicial = P * (1 + r)^n
Total Investido     = P + PMT * n
Rendimento Bruto    = (FV_inicial + FV_aportes) - Total Investido
Imposto de Renda    = Rendimento Bruto * t
Valor Final Liquido = FV_inicial + FV_aportes - Imposto de Renda
```
