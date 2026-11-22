"""Ponto de entrada na raiz para execucao direta via `python main.py <arquivo.dsl>`."""

import sys

from dsl_financeira.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
