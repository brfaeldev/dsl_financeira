"""
Interface de Linha de Comando - CLI (cli.py)

Gerencia a leitura de arquivos de script (.dsl) informados pelo usuario no
terminal, aciona o pipeline do interpretador e formata as saidas de erro
distinguindo falhas semanticas, sintaticas e de execucao.
"""

import argparse
import sys

from lark.exceptions import LarkError

from . import executar
from .erros import ErroSemantico


def _criar_arg_parser():
    parser = argparse.ArgumentParser(
        prog="dsl_financeira",
        description="Interpretador da DSL Financeira para modelagem e simulacao de investimentos.",
    )
    parser.add_argument(
        "arquivo",
        nargs="?",
        help="Caminho para o script .dsl a ser executado.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output",
        help="Diretorio de saida para os graficos gerados (padrao: output).",
    )
    return parser


def main(argv=None):
    """Executa um arquivo .dsl a partir dos argumentos de linha de comando."""
    if argv is None:
        argv = sys.argv

    arg_parser = _criar_arg_parser()
    try:
        args = arg_parser.parse_args(argv[1:])
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0

    if not args.arquivo:
        print("Uso: python -m dsl_financeira <arquivo.dsl>", file=sys.stderr)
        return 1

    caminho = args.arquivo
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            codigo = arquivo.read()
    except OSError as erro:
        print(f"Erro ao abrir o arquivo: {erro}", file=sys.stderr)
        return 1

    # Tratamento em tres camadas para distinguir falhas de dominio (Semantico),
    # falhas gramaticais/lexicas (LarkError) e erros inesperados de runtime.
    try:
        executar(codigo, diretorio_saida=args.output_dir)
    except ErroSemantico as erro:
        print(f"[Erro Semantico] {erro}", file=sys.stderr)
        return 1
    except LarkError as erro:
        print(f"[Erro de Sintaxe] {erro}", file=sys.stderr)
        return 1
    except Exception as erro:
        print(f"[Erro de Execucao] {erro}", file=sys.stderr)
        return 1

    return 0


def run():
    """Entry point para console_scripts (pyproject.toml)."""
    sys.exit(main(sys.argv))
