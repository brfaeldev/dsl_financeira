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
    extrair_declaracoes_script,
    gerar_bloco_investimento_dsl,
    gerar_declaracao_indice_dsl,
    inserir_bloco_investimento_dsl,
    inserir_ou_atualizar_indice_dsl,
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
            'INVESTIMENTO "TesteREPL" # comentario no inicio do bloco\n'
            "    VALOR_INICIAL 1000.00\n"
            "    PERIODO 12 MESES\n"
            '    TAXA 100.0 PORCENTO DO "CDI"\n'
            "FIM # comentario na linha de fechamento\n"
            "LISTAR\n"
            'IMPRIMIR RESUMO "TesteREPL"\n'
            "SAIR\n"
        )
        entrada = io.StringIO(sessao_repl)
        saida = io.StringIO()
        erro = io.StringIO()
        codigo = iniciar_repl(entrada=entrada, saida=saida, erro_saida=erro)
        self.assertEqual(codigo, 0)
        self.assertIn("[INDICE] CDI", saida.getvalue())
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

        bloco_sem_aporte = gerar_bloco_investimento_dsl(
            nome="ZeroAporte",
            valor_inicial=0.0,
            usar_aporte=True,
            aporte_mensal=0.0,
        )
        self.assertIn("VALOR_INICIAL 0.00", bloco_sem_aporte)

        # Valida a renderizacao completa da interface Streamlit via AppTest
        from streamlit.testing.v1 import AppTest

        caminho_app = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "app.py"
        )
        at = AppTest.from_file(caminho_app, default_timeout=30)
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertGreater(len(at.metric), 0)

    def test_playground_assistente_visual_e_sincronizacao(self):
        codigo_base = (
            '# INDICE "Ignorado" 1.0 PORCENTO AO_ANO\n'
            'INDICE "CDI" 10.75 PORCENTO AO_ANO\n'
            'INVESTIMENTO "Base"\n'
            "    VALOR_INICIAL 1000.00\n"
            "    PERIODO 12 MESES\n"
            "FIM\n"
        )
        decls = extrair_declaracoes_script(codigo_base)
        self.assertEqual(decls["indices"], ["CDI"])
        self.assertEqual(decls["investimentos"], ["Base"])

        # Atualiza indice existente sem duplicar e insere novo indice no topo
        atualizado, foi_atualizado = inserir_ou_atualizar_indice_dsl(
            codigo_base, "CDI", 11.25, "AO_ANO"
        )
        self.assertTrue(foi_atualizado)
        self.assertEqual(atualizado.count('INDICE "CDI"'), 1)
        self.assertIn('INDICE "CDI" 11.25 PORCENTO AO_ANO', atualizado)

        bloco = gerar_bloco_investimento_dsl(
            nome="Pos_IPCA",
            modo_taxa="Pos-Fixada (% de Indice)",
            taxa_valor=100.0,
            indice_taxa=' "CDI" ',
            modo_inflacao="Usar Indice",
            indice_inflacao="IPCA",
        )
        self.assertIn('TAXA 100.00 PORCENTO DO "CDI"', bloco)
        self.assertIn('INFLACAO "IPCA"', bloco)

        com_auto_indice = inserir_bloco_investimento_dsl(
            atualizado, bloco, indices_ausentes=["IPCA"]
        )
        self.assertIn('INDICE "IPCA" 4.50 PORCENTO AO_ANO', com_auto_indice)
        self.assertTrue(compilar_e_simular_dsl(com_auto_indice)["sucesso"])

        from streamlit.testing.v1 import AppTest

        caminho_app = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "app.py"
        )
        at = AppTest.from_file(caminho_app, default_timeout=30)
        at.run()

        # Edicao simultanea no editor + insercao via assistente preserva a edicao
        at.text_area[0].set_value(
            'INVESTIMENTO "Editado"\n'
            "    VALOR_INICIAL 2000.00\n"
            "    PERIODO 12 MESES\n"
            "    TAXA 1.0 PORCENTO AO_MES\n"
            "FIM\n"
        )
        at.sidebar.button[2].click()
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.error), 0)
        self.assertIn('INVESTIMENTO "Editado"', at.text_area[0].value)
        self.assertIn('INVESTIMENTO "Novo_Cenario"', at.text_area[0].value)

        # Inserir mesmo nome novamente bloqueia duplicidade sem quebrar o script
        at.sidebar.button[2].click().run()
        self.assertEqual(at.text_area[0].value.count('INVESTIMENTO "Novo_Cenario"'), 1)
        self.assertTrue(
            any("Novo_Cenario" in e.value for e in at.sidebar.error)
        )

        # Pos-Fixada oculta unidade, assume 100% e auto-declara indices ausentes
        at.sidebar.text_input[1].set_value("CDB_Pos")
        at.sidebar.selectbox[3].select("Pos-Fixada (% de Indice)").run()
        at.sidebar.selectbox[4].select("Usar Indice").run()
        at.sidebar.button[2].click().run()
        self.assertEqual(len(at.error), 0)
        self.assertIn('INDICE "CDI"', at.text_area[0].value)
        self.assertIn('INDICE "IPCA"', at.text_area[0].value)
        self.assertIn('TAXA 100.00 PORCENTO DO "CDI"', at.text_area[0].value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
