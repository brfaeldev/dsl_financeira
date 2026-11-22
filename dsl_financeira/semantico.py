"""Analise Semantica da DSL Financeira.

Implementa um AST Visitor usando a infraestrutura nativa da biblioteca Lark
(lark.visitors.Interpreter) para percorrer a AST, registrar as declaracoes de
investimento na Tabela de Simbolos e verificar restricoes de integridade
(e.g., taxas de juros nao negativas, prazos obrigatorios maiores que zero).
"""

from lark.visitors import Interpreter

from .erros import (
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)
from .tabela_simbolos import TabelaSimbolos, aliquota_regressiva_ir


def _texto(token):
    """Remove as aspas de um token STRING."""
    return str(token)[1:-1]


class AnalisadorSemantico(Interpreter):
    """AST Visitor (Lark Interpreter) responsavel por alimentar a Tabela de Simbolos."""

    def __init__(self):
        super().__init__()
        self.tabela = TabelaSimbolos()
        self._simbolo_atual = None
        self._vistos_atual = set()

    def analisar(self, ast):
        """Percorre a AST validando declaracoes, parametros e comandos."""
        self.visit(ast)
        return self.tabela

    # ------------------------------------------------------------------
    # Declaracoes e bloco de parametros
    # ------------------------------------------------------------------
    def declaracao(self, tree):
        identificador = _texto(tree.children[0])
        simbolo = self.tabela.declarar(identificador)

        self._simbolo_atual = simbolo
        self._vistos_atual = set()
        try:
            self.visit(tree.children[1])
            if "periodo_definido" not in self._vistos_atual or simbolo.periodo <= 0:
                raise ParametroObrigatorioError(
                    identificador,
                    "PERIODO <n> MESES ou APORTE <valor> POR <n> MESES",
                )
            if simbolo.imposto_regressivo:
                simbolo.imposto = aliquota_regressiva_ir(simbolo.periodo)
        finally:
            self._simbolo_atual = None
            self._vistos_atual = set()

    def _registrar_parametro(self, nome, grupo=None, rotulo_conflito=None):
        identificador = self._simbolo_atual.identificador
        if nome in self._vistos_atual:
            raise ParametroDuplicadoError(identificador, nome.upper())
        if grupo and grupo in self._vistos_atual:
            raise ParametroDuplicadoError(
                identificador, rotulo_conflito or grupo.upper()
            )
        self._vistos_atual.add(nome)
        if grupo:
            self._vistos_atual.add(grupo)

    def valor_inicial(self, tree):
        self._registrar_parametro("valor_inicial")
        simbolo = self._simbolo_atual
        valor = float(tree.children[0])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "VALOR_INICIAL",
                valor,
                "O valor inicial nao pode ser negativo.",
            )
        simbolo.valor_inicial = valor

    def aporte(self, tree):
        self._registrar_parametro("aporte", grupo="periodo_definido", rotulo_conflito="PERIODO")
        simbolo = self._simbolo_atual
        valor = float(tree.children[0])
        meses = int(tree.children[1])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE",
                valor,
                "O aporte mensal nao pode ser negativo.",
            )
        if meses <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE ... MESES",
                meses,
                "O periodo deve ser maior que zero.",
            )
        simbolo.aporte = valor
        simbolo.periodo = meses

    def periodo(self, tree):
        self._registrar_parametro("periodo", grupo="periodo_definido", rotulo_conflito="PERIODO")
        simbolo = self._simbolo_atual
        meses = int(tree.children[0])
        if meses <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "PERIODO ... MESES",
                meses,
                "O periodo deve ser maior que zero.",
            )
        simbolo.periodo = meses

    def taxa(self, tree):
        self._registrar_parametro("taxa")
        simbolo = self._simbolo_atual
        valor = float(tree.children[0])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA",
                valor,
                "A taxa de juros nao pode ser negativa.",
            )
        simbolo.taxa = valor / 100.0

    def imposto(self, tree):
        self._registrar_parametro("imposto", grupo="imposto_definido", rotulo_conflito="IMPOSTO")
        simbolo = self._simbolo_atual
        valor = float(tree.children[0])
        if valor < 0 or valor > 100:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "IMPOSTO",
                valor,
                "A aliquota deve estar entre 0 e 100 porcento.",
            )
        simbolo.imposto = valor / 100.0

    def imposto_regressivo(self, tree):
        self._registrar_parametro(
            "imposto_regressivo", grupo="imposto_definido", rotulo_conflito="IMPOSTO"
        )
        self._simbolo_atual.imposto_regressivo = True

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------
    def imprimir_resumo(self, tree):
        identificador = _texto(tree.children[0])
        self.tabela.buscar(identificador)

    def gerar_grafico(self, tree):
        for token in tree.children:
            self.tabela.buscar(_texto(token))

    def comparar_grafico(self, tree):
        for token in tree.children:
            self.tabela.buscar(_texto(token))
