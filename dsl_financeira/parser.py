"""Front-End da DSL Financeira: Lexer e Parser (biblioteca Lark).

O codigo de entrada '.dsl' e convertido em tokens pelo Lexer e validado pela
gramatica no Parser, resultando na AST.
"""

import functools
import os

from lark import Lark

_CAMINHO_GRAMATICA = os.path.join(os.path.dirname(__file__), "gramatica.lark")


@functools.lru_cache(maxsize=1)
def carregar_gramatica():
    """Le o arquivo EBNF (.lark) do disco uma unica vez e mantem em memoria."""
    with open(_CAMINHO_GRAMATICA, "r", encoding="utf-8") as arquivo:
        return arquivo.read()


@functools.lru_cache(maxsize=4)
def criar_parser(parser="lalr"):
    """Cria (e armazena em cache) o parser da DSL.

    Suporta os geradores de parsers eficientes da Lark: LALR(1) (complexidade
    linear O(n) para gramaticas livres de contexto sem ambiguidade) e Earley,
    propagando metadados de linha e coluna para os nos da AST.
    """
    return Lark(
        carregar_gramatica(),
        start="programa",
        parser=parser,
        # Propaga line/column dos tokens folha para tree.meta nos nos internos da AST
        propagate_positions=True,
    )


def analisar(codigo, parser="lalr"):
    """Executa a analise lexica e sintatica, retornando a AST."""
    return criar_parser(parser).parse(codigo)
