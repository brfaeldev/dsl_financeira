"""
Interface de Linha de Comando e REPL Interativo - CLI (cli.py)

Gerencia a leitura de arquivos de script (.dsl) informados pelo usuario no
terminal ou a execucao do modo interativo REPL (`--repl` / `-i`), acionando o
pipeline do interpretador e formatando as saidas de erro.
"""

import argparse
import contextlib
import sys

from lark.exceptions import LarkError

from . import AnalisadorSemantico, Interpretador, analisar, executar
from .erros import ErroSemantico


def _criar_arg_parser():
    """Configura e retorna o parser de argumentos da linha de comando (argparse)."""
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
        help="Diretorio de saida para os graficos e arquivos gerados (padrao: output).",
    )
    parser.add_argument(
        "-i",
        "--repl",
        action="store_true",
        help="Inicia o terminal interativo (REPL) mantendo a Tabela de Simbolos viva em memoria.",
    )
    return parser


def _remover_comentario_linha(linha):
    """Remove comentario iniciado por '#' fora de literais entre aspas duplas."""
    em_aspas = False
    for idx, ch in enumerate(linha):
        if ch == '"':
            em_aspas = not em_aspas
        elif ch == "#" and not em_aspas:
            return linha[:idx].strip()
    return linha.strip()


def iniciar_repl(diretorio_saida="output", entrada=None, saida=None, erro_saida=None):
    """Executa o Read-Eval-Print Loop (REPL) da DSL Financeira."""
    stream_in = entrada if entrada is not None else sys.stdin
    stream_out = saida if saida is not None else sys.stdout
    stream_err = erro_saida if erro_saida is not None else sys.stderr

    analisador = AnalisadorSemantico()
    interpretador = Interpretador(analisador.tabela, diretorio_saida=diretorio_saida)

    print(
        "DSL Financeira - Modo Interativo (REPL). Digite 'SAIR' para encerrar.",
        file=stream_out,
    )
    buffer_bloco = []
    em_bloco = False

    while True:
        prompt = "... " if em_bloco else "dsl> "
        print(prompt, end="", file=stream_out, flush=True)
        linha = stream_in.readline()
        if not linha:
            break

        texto = _remover_comentario_linha(linha)
        if not texto:
            continue

        comando_upper = texto.upper()
        if comando_upper in ("SAIR", "EXIT", "QUIT"):
            break

        if not em_bloco and comando_upper == "LISTAR":
            indices = analisador.tabela.listar_indices()
            simbolos = analisador.tabela.listar()
            if not indices and not simbolos:
                print("Nenhum investimento declarado.", file=stream_out)
            else:
                for nome_ind, taxa_ind in indices.items():
                    print(
                        f"- [INDICE] {nome_ind} (r={taxa_ind * 100:.4f}% a.m.)",
                        file=stream_out,
                    )
                for s in simbolos:
                    print(
                        f"- {s.identificador} (P={s.valor_inicial}, PMT={s.aporte}, "
                        f"n={s.periodo}m, r={s.taxa * 100:.4f}% a.m.)",
                        file=stream_out,
                    )
            continue

        if (
            not em_bloco
            and comando_upper.startswith("INVESTIMENTO ")
            and not comando_upper.endswith(" FIM")
        ):
            em_bloco = True
            buffer_bloco = [linha]
            continue

        if em_bloco:
            buffer_bloco.append(linha)
            if comando_upper == "FIM" or comando_upper.endswith(" FIM"):
                em_bloco = False
                trecho = "".join(buffer_bloco)
                buffer_bloco = []
            else:
                continue
        else:
            trecho = linha

        try:
            ast = analisar(trecho)
            analisador.analisar(ast)
            with contextlib.redirect_stdout(stream_out):
                interpretador.executar(ast)
        except ErroSemantico as erro:
            print(f"[Erro Semantico] {erro}", file=stream_err)
        except LarkError as erro:
            print(f"[Erro de Sintaxe] {erro}", file=stream_err)
        except Exception as erro:
            print(f"[Erro de Execucao] {erro}", file=stream_err)

    return 0


def main(argv=None):
    """Executa um arquivo .dsl ou inicia o REPL a partir dos argumentos de linha de comando."""
    if argv is None:
        argv = sys.argv

    arg_parser = _criar_arg_parser()
    try:
        args = arg_parser.parse_args(argv[1:])
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0

    if args.repl:
        return iniciar_repl(diretorio_saida=args.output_dir)

    if not args.arquivo:
        print(
            "Uso: python -m dsl_financeira <arquivo.dsl> (ou use --repl para modo interativo)",
            file=sys.stderr,
        )
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
