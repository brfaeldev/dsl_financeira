"""DSL Financeira - Especificacao e Projeto de uma Linguagem de Dominio
Especifico (DSL) para Modelagem e Simulacao Financeira de Investimentos.

Pipeline: Codigo Source -> Parser -> AST -> Execucao
"""

from .erros import (
    DeclaracaoDuplicadaError,
    ErroSemantico,
    InvestimentoNaoDeclaradoError,
    ValorForaDoDominioError,
)
from .interpretador import Interpretador
from .parser import analisar, criar_parser
from .semantico import AnalisadorSemantico
from .tabela_simbolos import Investimento, TabelaSimbolos

__all__ = [
    "analisar",
    "criar_parser",
    "AnalisadorSemantico",
    "Interpretador",
    "TabelaSimbolos",
    "Investimento",
    "ErroSemantico",
    "DeclaracaoDuplicadaError",
    "InvestimentoNaoDeclaradoError",
    "ValorForaDoDominioError",
]


def executar(codigo):
    """Executa o pipeline completo: Parser -> AST -> Semantico -> Execucao."""
    ast = analisar(codigo)
    tabela = AnalisadorSemantico().analisar(ast)
    Interpretador(tabela).executar(ast)
    return tabela
