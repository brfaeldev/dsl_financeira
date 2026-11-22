"""Analise Semantica da DSL Financeira.

Uma classe inspetora percorre a AST, registrando as declaracoes de investimento
na Tabela de Simbolos e verificando restricoes de integridade (e.g., taxas de
juros nao negativas, prazos maiores que zero).
"""

from lark import Tree

from .erros import ValorForaDoDominioError
from .tabela_simbolos import TabelaSimbolos


def _texto(token):
    """Remove as aspas de um token STRING."""
    return str(token)[1:-1]


class AnalisadorSemantico:
    """Inspetor da AST responsavel por alimentar a Tabela de Simbolos."""

    def __init__(self):
        self.tabela = TabelaSimbolos()

    def analisar(self, ast):
        for no in ast.children:
            if not isinstance(no, Tree):
                continue
            if no.data == "declaracao":
                self._visitar_declaracao(no)
            elif no.data in ("imprimir_resumo", "gerar_grafico"):
                self._visitar_comando(no)
        return self.tabela

    # ------------------------------------------------------------------
    # Declaracoes
    # ------------------------------------------------------------------
    def _visitar_declaracao(self, no):
        identificador = _texto(no.children[0])
        simbolo = self.tabela.declarar(identificador)

        bloco = no.children[1]
        for parametro in bloco.children:
            self._visitar_parametro(simbolo, parametro)

    def _visitar_parametro(self, simbolo, parametro):
        nome = parametro.data

        if nome == "valor_inicial":
            valor = float(parametro.children[0])
            if valor < 0:
                raise ValorForaDoDominioError(
                    simbolo.identificador, "VALOR_INICIAL", valor,
                    "O valor inicial nao pode ser negativo.",
                )
            simbolo.valor_inicial = valor

        elif nome == "aporte":
            valor = float(parametro.children[0])
            meses = int(parametro.children[1])
            if valor < 0:
                raise ValorForaDoDominioError(
                    simbolo.identificador, "APORTE", valor,
                    "O aporte mensal nao pode ser negativo.",
                )
            if meses <= 0:
                raise ValorForaDoDominioError(
                    simbolo.identificador, "APORTE ... MESES", meses,
                    "O periodo deve ser maior que zero.",
                )
            simbolo.aporte = valor
            simbolo.periodo = meses

        elif nome == "taxa":
            valor = float(parametro.children[0])
            if valor < 0:
                raise ValorForaDoDominioError(
                    simbolo.identificador, "TAXA", valor,
                    "A taxa de juros nao pode ser negativa.",
                )
            simbolo.taxa = valor / 100.0

        elif nome == "imposto":
            valor = float(parametro.children[0])
            if valor < 0 or valor > 100:
                raise ValorForaDoDominioError(
                    simbolo.identificador, "IMPOSTO", valor,
                    "A aliquota deve estar entre 0 e 100 porcento.",
                )
            simbolo.imposto = valor / 100.0

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------
    def _visitar_comando(self, no):
        identificador = _texto(no.children[0])
        # Lanca InvestimentoNaoDeclaradoError caso o simbolo nao exista.
        self.tabela.buscar(identificador)
