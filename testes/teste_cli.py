"""
Testes de CLI, REPL Interativo, Gramatica TextMate e Playground (teste_cli.py)

Valida a interface de linha de comando (cli.py), o modo interativo REPL, o
manifesto de syntax highlighting para VS Code e os servicos do Playground Web
(`dsl_financeira.playground`).
"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from dsl_financeira.cli import iniciar_repl, main as cli_main
from dsl_financeira.playground import (
    compilar_e_simular_dsl,
    gerar_bloco_investimento_dsl,
    gerar_declaracao_indice_dsl,
    listar_exemplos_disponiveis,
)
from testes.teste_motor import CENARIO_APOSENTADORIA


class TestCLI(unittest.TestCase):
    """Valida a interface de linha de comando (cli.py), REPL e servicos do Playground."""

    def test_cli_execucao_sucesso_e_help(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "teste.dsl")
            with open(script, "w", encoding="utf-8") as f:
                f.write(CENARIO_APOSENTADORIA)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                codigo_saida = cli_main(["dsl_financeira", script, "-o", tmpdir])
            self.assertEqual(codigo_saida, 0)
            self.assertIn("RESUMO DO INVESTIMENTO: Aposentadoria", out.getvalue())

            out_help = io.StringIO()
            with contextlib.redirect_stdout(out_help):
                codigo_help = cli_main(["dsl_financeira", "--help"])
            self.assertEqual(codigo_help, 0)

    def test_cli_erros_arquivo_sintaxe_e_semantico(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli_main(["dsl_financeira"]), 1)
            self.assertEqual(cli_main(["dsl_financeira", "nao_existe.dsl"]), 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            arq_sintaxe = os.path.join(tmpdir, "erro_sintaxe.dsl")
            with open(arq_sintaxe, "w", encoding="utf-8") as f:
                f.write('INVESTIMENTO "Invalido" COMANDO_DESCONHECIDO FIM')

            err_sintaxe = io.StringIO()
            with contextlib.redirect_stderr(err_sintaxe):
                self.assertEqual(cli_main(["dsl_financeira", arq_sintaxe]), 1)
            self.assertIn("[Erro de Sintaxe]", err_sintaxe.getvalue())

            arq_semantico = os.path.join(tmpdir, "erro_semantico.dsl")
            with open(arq_semantico, "w", encoding="utf-8") as f:
                f.write('IMPRIMIR RESUMO "NaoExiste"')

            err_semantico = io.StringIO()
            with contextlib.redirect_stderr(err_semantico):
                self.assertEqual(cli_main(["dsl_financeira", arq_semantico]), 1)
            self.assertIn("[Erro Semantico]", err_semantico.getvalue())

    def test_repl_interativo_e_gramatica_vscode(self):
        sessao_repl = (
            'INDICE "CDI" 1.0 PORCENTO AO_MES\n'
            'INVESTIMENTO "TesteREPL"\n'
            "    VALOR_INICIAL 1000.00\n"
            "    PERIODO 12 MESES\n"
            '    TAXA 100.0 PORCENTO DO "CDI"\n'
            "FIM\n"
            "LISTAR\n"
            'IMPRIMIR RESUMO "TesteREPL"\n'
            "SAIR\n"
        )
        entrada = io.StringIO(sessao_repl)
        saida = io.StringIO()
        erro = io.StringIO()
        codigo = iniciar_repl(entrada=entrada, saida=saida, erro_saida=erro)
        self.assertEqual(codigo, 0)
        self.assertIn("TesteREPL", saida.getvalue())
        self.assertIn("RESUMO DO INVESTIMENTO: TesteREPL", saida.getvalue())

        caminho_tm = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vscode-dsl-financeira",
            "syntaxes",
            "dsl.tmLanguage.json",
        )
        self.assertTrue(os.path.exists(caminho_tm))
        with open(caminho_tm, "r", encoding="utf-8") as f:
            gramatica_tm = json.load(f)
        self.assertEqual(gramatica_tm["scopeName"], "source.dsl-financeira")

    def test_playground_streamlit_funcoes_core(self):
        exemplos = listar_exemplos_disponiveis()
        self.assertIn("aposentadoria.dsl", exemplos)

        cod_ind = gerar_declaracao_indice_dsl("CDI", 10.75, "AO_ANO")
        cod_inv = gerar_bloco_investimento_dsl(
            nome="CDB_Playground",
            valor_inicial=5000.0,
            usar_aporte=True,
            aporte_mensal=500.0,
            prazo=12,
            unidade_prazo="MESES",
            modo_taxa="Pos-Fixada (% de Indice)",
            taxa_valor=110.0,
            indice_taxa="CDI",
            modo_imposto="REGRESSIVO",
        )
        script_completo = f"{cod_ind}\n{cod_inv}\n"
        res = compilar_e_simular_dsl(script_completo)
        self.assertTrue(res["sucesso"])
        self.assertEqual(len(res["resultados"]), 1)
        self.assertIn("RESUMO DO INVESTIMENTO: CDB_Playground", res["console_output"])
        self.assertGreater(len(res["tokens"]), 5)
        self.assertIn("declaracao", res["ast_pretty"])

        res_erro = compilar_e_simular_dsl('IMPRIMIR RESUMO "NaoDeclarado"')
        self.assertFalse(res_erro["sucesso"])
        self.assertEqual(res_erro["tipo_erro"], "Semantico")


if __name__ == "__main__":
    unittest.main(verbosity=2)
