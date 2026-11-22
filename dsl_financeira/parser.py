"""Front-End da DSL Financeira: Lexer e Parser (biblioteca Lark).

O codigo de entrada '.dsl' e convertido em tokens pelo Lexer e validado pela
gramatica no Parser, resultando na AST.
"""

import os

from lark import Lark

_CAMINHO_GRAMATICA = os.path.join(os.path.dirname(__file__), "gramatica.lark")


def carregar_gramatica():
    with open(_CAMINHO_GRAMATICA, "r", encoding="utf-8") as arquivo:
        return arquivo.read()


def criar_parser(parser="lalr"):
    """Cria o parser da DSL.

    Suporta os geradores de parsers eficientes da Lark: LALR(1) e Earley.
    """
    return Lark(
        carregar_gramatica(),
        start="programa",
        parser=parser,
    )


def analisar(codigo, parser="lalr"):
    """Executa a analise lexica e sintatica, retornando a AST."""
    return criar_parser(parser).parse(codigo)
