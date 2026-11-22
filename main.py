"""
Ponto de Entrada Principal da Aplicacao (main.py)

Atalho de execucao na raiz do projeto que delega os argumentos recebidos via
terminal para a Interface de Linha de Comando (CLI) do pacote dsl_financeira.
"""

import sys

from dsl_financeira.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
