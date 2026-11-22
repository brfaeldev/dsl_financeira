"""
Testes de Renderizacao Grafica e Exportacao de Artefatos (teste_saidas.py)

Valida a geracao de graficos PNG (individuais e comparativos), sanitizacao e
prevencao de colisao de nomes de arquivos, graficos HTML interativos (Plotly),
exportacoes CSV/JSON e relatorios consolidados em Markdown.
"""

import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

from dsl_financeira import executar


class TestGeracaoGraficos(unittest.TestCase):
    """Valida a geracao de graficos, exportacoes CSV/JSON/HTML e relatorios Markdown."""

    def test_gerar_grafico_individual(self):
        codigo = """
        INVESTIMENTO "Reserva"
            VALOR_INICIAL 1000.00
            APORTE 100.00 POR 24 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        GERAR GRAFICO "Reserva"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "grafico_Reserva.png")
            executar(codigo, diretorio_saida=tmpdir)
            self.assertTrue(os.path.exists(caminho))

    def test_sanitizacao_nome_arquivo_grafico(self):
        codigo = """
        INVESTIMENTO "CDB 110% / Liquidez: Diaria"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 0.9 PORCENTO AO_MES
        FIM
        GERAR GRAFICO "CDB 110% / Liquidez: Diaria"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "grafico_CDB_110%_Liquidez_Diaria.png")
            executar(codigo, diretorio_saida=tmpdir)
            self.assertTrue(os.path.exists(caminho))

    def test_comparar_grafico_multiplos_cenarios(self):
        codigo = """
        INVESTIMENTO "CenarioA"
            VALOR_INICIAL 5000.00
            APORTE 500.00 POR 12 MESES
            TAXA 0.8 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        INVESTIMENTO "CenarioB"
            VALOR_INICIAL 5000.00
            APORTE 500.00 POR 12 MESES
            TAXA 1.05 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM
        COMPARAR GRAFICO "CenarioA" "CenarioB"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(
                tmpdir, "grafico_comparativo_CenarioA_vs_CenarioB.png"
            )
            executar(codigo, diretorio_saida=tmpdir)
            self.assertTrue(os.path.exists(caminho))

    def test_gerar_grafico_multiplos_cenarios_delega_para_comparativo(self):
        codigo = """
        INVESTIMENTO "A"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 0.8 PORCENTO AO_MES
        FIM
        INVESTIMENTO "B"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
        FIM
        GERAR GRAFICO "A" "B"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = os.path.join(tmpdir, "grafico_comparativo_A_vs_B.png")
            executar(codigo, diretorio_saida=tmpdir)
            self.assertTrue(os.path.exists(caminho))

    def test_prevencao_colisao_nomes_arquivos_sanitizados(self):
        codigo = """
        INVESTIMENTO "CDB 1"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
        FIM
        INVESTIMENTO "CDB/1"
            VALOR_INICIAL 2000.00
            PERIODO 12 MESES
        FIM
        GERAR GRAFICO "CDB 1"
        GERAR GRAFICO "CDB/1"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            executar(codigo, diretorio_saida=tmpdir)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "grafico_CDB_1.png")))
            self.assertTrue(
                os.path.exists(os.path.join(tmpdir, "grafico_CDB_1_2.png"))
            )

    def test_exportar_csv_json_grafico_interativo_e_relatorio(self):
        codigo = """
        INVESTIMENTO "A"
            VALOR_INICIAL 5000.00
            APORTE 500.00 POR 12 MESES
            TAXA 0.8 PORCENTO AO_MES
            INFLACAO 0.35 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        INVESTIMENTO "B"
            VALOR_INICIAL 5000.00
            APORTE 500.00 POR 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM
        EXPORTAR CSV "A"
        EXPORTAR JSON "A" "B"
        GERAR GRAFICO_INTERATIVO "A" "B"
        GERAR RELATORIO "relatorio_teste.md"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                executar(codigo, diretorio_saida=tmpdir)

            arq_csv = os.path.join(tmpdir, "evolucao_A.csv")
            arq_json = os.path.join(tmpdir, "evolucao_comparativa_A_vs_B.json")
            arq_html = os.path.join(
                tmpdir, "grafico_interativo_comparativo_A_vs_B.html"
            )
            arq_md = os.path.join(tmpdir, "relatorio_teste.md")

            self.assertTrue(os.path.exists(arq_csv))
            self.assertTrue(os.path.exists(arq_json))
            self.assertTrue(os.path.exists(arq_html))
            self.assertTrue(os.path.exists(arq_md))

            with open(arq_csv, "r", encoding="utf-8") as f:
                linhas_csv = list(csv.DictReader(f))
            self.assertEqual(len(linhas_csv), 13)  # mes 0 ate 12

            with open(arq_json, "r", encoding="utf-8") as f:
                dados_json = json.load(f)
            self.assertEqual(len(dados_json["investimentos"]), 2)

            with open(arq_md, "r", encoding="utf-8") as f:
                texto_md = f.read()
            self.assertIn("Relatorio Consolidado de Simulacao Financeira", texto_md)

    def test_sanitizacao_relatorio_com_extensao_md_e_escape_html(self):
        codigo = """
        INVESTIMENTO "CDB <Teste>"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
        FIM
        GERAR GRAFICO_INTERATIVO "CDB <Teste>"
        GERAR RELATORIO "relatorio: cenario?.md"
        GERAR RELATORIO "relatorio/cenario?.md"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                executar(codigo, diretorio_saida=tmpdir)

            arq_rel1 = os.path.join(tmpdir, "relatorio_cenario.md")
            arq_rel2 = os.path.join(tmpdir, "relatorio_cenario_2.md")
            arq_html = os.path.join(tmpdir, "grafico_interativo_CDB_Teste.html")
            self.assertTrue(os.path.exists(arq_rel1))
            self.assertTrue(os.path.exists(arq_rel2))
            self.assertTrue(os.path.exists(arq_html))

            with open(arq_html, "r", encoding="utf-8") as f:
                html_gerado = f.read()
            self.assertIn("&lt;Teste&gt;", html_gerado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
