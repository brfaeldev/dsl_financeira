"""
Nucleo e API Publica do Pacote (dsl_financeira/__init__.py)

Centraliza e expoe as classes e funcoes principais do interpretador (Parser,
Tabela de Simbolos, Analisador Semantico, Motor de Execucao e Excecoes), alem
de fornecer a funcao fachada `executar()` que orquestra o pipeline completo.
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
    """Executa o pipeline completo: Parser -> AST -> Semantico -> Execucao.

    Retorna a `TabelaSimbolos` populada para permitir inspecao programatica
    (por exemplo, na suite de testes automatizados).
    """
    ast = analisar(codigo)
    tabela = AnalisadorSemantico().analisar(ast)
    Interpretador(tabela).executar(ast)
    return tabela
