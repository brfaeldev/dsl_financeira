"""Interface de Linha de Comando (CLI) da DSL Financeira."""

import sys

from lark.exceptions import LarkError

from . import executar
from .erros import ErroSemantico


def main(argv=None):
    """Executa um arquivo .dsl a partir dos argumentos de linha de comando."""
    if argv is None:
        argv = sys.argv

    if len(argv) != 2:
        print("Uso: python -m dsl_financeira <arquivo.dsl>")
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
    except LarkError as erro:
        print(f"[Erro de Sintaxe] {erro}")
        return 1
    except Exception as erro:
        print(f"[Erro de Execucao] {erro}")
        return 1

    return 0


def run():
    """Entry point para console_scripts (pyproject.toml)."""
    sys.exit(main(sys.argv))
