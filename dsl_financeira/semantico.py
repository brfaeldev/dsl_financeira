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
    """Remove as aspas externas de um token literal STRING (ex.: '"CDB"' -> 'CDB')."""
    return str(token)[1:-1]


def _posicao(no):
    """Extrai (linha, coluna) de um no Tree (via meta) ou Token folha do Lark."""
    if hasattr(no, "meta") and not getattr(no.meta, "empty", True):
        return getattr(no.meta, "line", None), getattr(no.meta, "column", None)
    return getattr(no, "line", None), getattr(no, "column", None)


class AnalisadorSemantico(Interpreter):
    """AST Visitor (Lark Interpreter) responsavel por alimentar a Tabela de Simbolos.

    Diferente de lark.Visitor (bottom-up), a classe Interpreter percorre a AST
    top-down, permitindo controlar o contexto do bloco INVESTIMENTO atual antes
    de visitar seus parametros filhos.
    """

    def __init__(self):
        super().__init__()
        self.tabela = TabelaSimbolos()
        # Contexto temporario do bloco INVESTIMENTO sendo validado no momento
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
        linha, coluna = _posicao(tree)
        simbolo = self.tabela.declarar(identificador, linha=linha, coluna=coluna)

        self._simbolo_atual = simbolo
        self._vistos_atual = set()
        try:
            # Visita o no bloco_parametros, disparando os metodos de cada parametro
            self.visit(tree.children[1])

            # Todo investimento precisa ter um horizonte temporal (> 0 meses),
            # definido via PERIODO <n> MESES ou via APORTE <v> POR <n> MESES.
            if "periodo_definido" not in self._vistos_atual or simbolo.periodo <= 0:
                raise ParametroObrigatorioError(
                    identificador,
                    "PERIODO <n> MESES ou APORTE <valor> POR <n> MESES",
                    linha=linha,
                    coluna=coluna,
                )

            # A aliquota regressiva depende do prazo final (n), por isso e
            # resolvida ao encerrar a leitura de todos os parametros do bloco.
            if simbolo.imposto_regressivo:
                simbolo.imposto = aliquota_regressiva_ir(simbolo.periodo)
        finally:
            # Garante limpeza do estado de bloco mesmo se uma excecao for lancada
            self._simbolo_atual = None
            self._vistos_atual = set()

    def _registrar_parametro(self, nome, tree, grupo=None, rotulo_conflito=None):
        """Registra a ocorrencia de um parametro no bloco atual e impede duplicatas.

        O argumento `grupo` permite bloquear parametros mutuamente exclusivos
        (ex.: declarar APORTE ... POR <n> MESES e PERIODO <n> MESES juntos, ou
        IMPOSTO <x> PORCENTO e IMPOSTO REGRESSIVO no mesmo investimento).
        """
        identificador = self._simbolo_atual.identificador
        linha, coluna = _posicao(tree)
        if nome in self._vistos_atual:
            raise ParametroDuplicadoError(
                identificador, nome.upper(), linha=linha, coluna=coluna
            )
        if grupo and grupo in self._vistos_atual:
            raise ParametroDuplicadoError(
                identificador,
                rotulo_conflito or grupo.upper(),
                linha=linha,
                coluna=coluna,
            )
        self._vistos_atual.add(nome)
        if grupo:
            self._vistos_atual.add(grupo)

    def valor_inicial(self, tree):
        self._registrar_parametro("valor_inicial", tree)
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "VALOR_INICIAL",
                valor,
                "O valor inicial nao pode ser negativo.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.valor_inicial = valor

    def aporte(self, tree):
        self._registrar_parametro(
            "aporte", tree, grupo="periodo_definido", rotulo_conflito="PERIODO"
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        meses = int(tree.children[1])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE",
                valor,
                "O aporte mensal nao pode ser negativo.",
                linha=linha,
                coluna=coluna,
            )
        if meses <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE ... MESES",
                meses,
                "O periodo deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.aporte = valor
        simbolo.periodo = meses

    def periodo(self, tree):
        self._registrar_parametro(
            "periodo", tree, grupo="periodo_definido", rotulo_conflito="PERIODO"
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        meses = int(tree.children[0])
        if meses <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "PERIODO ... MESES",
                meses,
                "O periodo deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.periodo = meses

    def taxa(self, tree):
        self._registrar_parametro("taxa", tree)
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA",
                valor,
                "A taxa de juros nao pode ser negativa.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.taxa = valor / 100.0

    def imposto(self, tree):
        self._registrar_parametro(
            "imposto", tree, grupo="imposto_definido", rotulo_conflito="IMPOSTO"
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        if valor < 0 or valor > 100:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "IMPOSTO",
                valor,
                "A aliquota deve estar entre 0 e 100 porcento.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.imposto = valor / 100.0

    def imposto_regressivo(self, tree):
        self._registrar_parametro(
            "imposto_regressivo",
            tree,
            grupo="imposto_definido",
            rotulo_conflito="IMPOSTO",
        )
        self._simbolo_atual.imposto_regressivo = True

    # ------------------------------------------------------------------
    # Comandos (validacao de escopo declare-before-use e argumentos)
    # ------------------------------------------------------------------
    def _validar_identificadores_comando(self, tree, nome_comando):
        """Verifica se os investimentos referenciados existem e nao se repetem no comando."""
        vistos = set()
        for token in tree.children:
            identificador = _texto(token)
            linha, coluna = _posicao(token)
            self.tabela.buscar(identificador, linha=linha, coluna=coluna)
            if identificador in vistos:
                raise ParametroDuplicadoError(
                    identificador,
                    nome_comando,
                    mensagem=(
                        f"Comando '{nome_comando}': o investimento "
                        f"'{identificador}' foi informado mais de uma vez."
                    ),
                    linha=linha,
                    coluna=coluna,
                )
            vistos.add(identificador)

    def imprimir_resumo(self, tree):
        token = tree.children[0]
        linha, coluna = _posicao(token)
        self.tabela.buscar(_texto(token), linha=linha, coluna=coluna)

    def gerar_grafico(self, tree):
        self._validar_identificadores_comando(tree, "GERAR GRAFICO")

    def comparar_grafico(self, tree):
        self._validar_identificadores_comando(tree, "COMPARAR GRAFICO")
