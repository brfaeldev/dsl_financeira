"""
Ponto de Entrada do Modulo Executavel (__main__.py)

Habilita a execucao direta do pacote como modulo Python (`python -m dsl_financeira`),
encaminhando os parametros do sistema operacional para o controlador da CLI.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
