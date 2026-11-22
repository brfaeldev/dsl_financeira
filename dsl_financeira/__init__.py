"""DSL Financeira - Especificacao e Projeto de uma Linguagem de Dominio
Especifico (DSL) para Modelagem e Simulacao Financeira de Investimentos.

Pipeline: Codigo Source -> Parser -> AST -> Execucao
"""

from .erros import (
    DeclaracaoDuplicadaError,
    ErroSemantico,
    InvestimentoNaoDeclaradoError,
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)
from .interpretador import Interpretador, Resultado
from .parser import analisar, criar_parser
from .semantico import AnalisadorSemantico
from .tabela_simbolos import Investimento, TabelaSimbolos, aliquota_regressiva_ir

__all__ = [
    "analisar",
    "criar_parser",
    "executar",
    "AnalisadorSemantico",
    "Interpretador",
    "Resultado",
    "TabelaSimbolos",
    "Investimento",
    "aliquota_regressiva_ir",
    "ErroSemantico",
    "DeclaracaoDuplicadaError",
    "InvestimentoNaoDeclaradoError",
    "ParametroDuplicadoError",
    "ParametroObrigatorioError",
    "ValorForaDoDominioError",
]


def executar(codigo):
    """Executa o pipeline completo: Parser -> AST -> Semantico -> Execucao."""
    ast = analisar(codigo)
    tabela = AnalisadorSemantico().analisar(ast)
    Interpretador(tabela).executar(ast)
    return tabela
