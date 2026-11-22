"""Ponto de entrada do interpretador da DSL Financeira.

Uso:
    python main.py exemplos/aposentadoria.dsl
"""

import sys

from dsl_financeira import executar
from dsl_financeira.erros import ErroSemantico


def main(argv):
    if len(argv) != 2:
        print("Uso: python main.py <arquivo.dsl>")
        return 1

    caminho = argv[1]
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            codigo = arquivo.read()
    except OSError as erro:
        print(f"Erro ao abrir o arquivo: {erro}")
        return 1

    try:
        executar(codigo)
    except ErroSemantico as erro:
        print(f"[Erro Semantico] {erro}")
        return 1
    except Exception as erro:  # erros de analise lexica/sintatica
        print(f"[Erro de Sintaxe] {erro}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
