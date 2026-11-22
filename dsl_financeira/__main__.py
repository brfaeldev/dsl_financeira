"""Permite executar o pacote diretamente via `python -m dsl_financeira <arquivo.dsl>`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
