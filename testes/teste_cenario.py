"""
Suite de Testes Automatizados da DSL Financeira (teste_cenario.py)

Valida a aderencia arquitetural do compilador/interpretador (padrao Visitor e
cache do parser), a precisao matematica das simulacoes financeiras, a captura de
erros semanticos e a geracao de graficos individuais e comparativos.
"""

import contextlib
import io
import os
import tempfile
import unittest

from lark.visitors import Interpreter

from dsl_financeira import (
    AnalisadorSemantico,
    Interpretador,
    Resultado,
    analisar,
    criar_parser,
    executar,
)
from dsl_financeira.cli import main as cli_main
from dsl_financeira.erros import (
    DeclaracaoDuplicadaError,
    InvestimentoNaoDeclaradoError,
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)

CENARIO_APOSENTADORIA = """
INVESTIMENTO "Aposentadoria"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 0.8 PORCENTO AO_MES
    IMPOSTO 15.0 PORCENTO
FIM

IMPRIMIR RESUMO "Aposentadoria"
"""


class TestArquiteturaCompilador(unittest.TestCase):
    """Valida a aderencia arquitetural aos padroes de projeto descritos no artigo."""

    def test_heranca_nativa_visitor_lark(self):
        self.assertTrue(issubclass(AnalisadorSemantico, Interpreter))
        self.assertTrue(issubclass(Interpretador, Interpreter))

    def test_cache_instancia_parser(self):
        self.assertIs(criar_parser("lalr"), criar_parser("lalr"))

    def test_compatibilidade_parser_earley_e_inteiros_em_campos_decimais(self):
        codigo = """
        INVESTIMENTO "Inteiros"
            VALOR_INICIAL 5000
            APORTE 500 POR 12 MESES
            TAXA 1 PORCENTO AO_MES
            IMPOSTO 15 PORCENTO
        FIM
        """
        ast_lalr = analisar(codigo, parser="lalr")
        ast_earley = analisar(codigo, parser="earley")
        self.assertEqual(ast_lalr, ast_earley)
        tabela = executar(codigo, parser="earley")
        simbolo = tabela.buscar("Inteiros")
        self.assertEqual(simbolo.valor_inicial, 5000.0)
        self.assertEqual(simbolo.aporte, 500.0)
        self.assertAlmostEqual(simbolo.taxa, 0.01, places=12)
        self.assertAlmostEqual(simbolo.imposto, 0.15, places=12)


class TestSimulacaoFinanceira(unittest.TestCase):
    """Valida os calculos matematicos e tributarios do motor de execucao."""

    def test_cenario_proposto_artigo(self):
        """Valida o cenario base 'Aposentadoria' (Secao IV-A do artigo IEEE)."""
        tabela = executar(CENARIO_APOSENTADORIA)
        simbolo = tabela.buscar("Aposentadoria")

        self.assertEqual(simbolo.valor_inicial, 5000.00)
        self.assertEqual(simbolo.aporte, 500.00)
        self.assertEqual(simbolo.periodo, 12)
        self.assertAlmostEqual(simbolo.taxa, 0.008, places=12)
        self.assertAlmostEqual(simbolo.imposto, 0.15, places=12)

        # FV_inicial = 5000 * (1.008)^12 = 5501.69
        # FV_aportes = 500 * ((1.008)^12 - 1) / 0.008 = 6271.17
        # Rendimento Bruto = (5501.69 + 6271.17) - 11000 = 772.86
        resultado = Resultado(simbolo)
        self.assertEqual(round(resultado.total_investido, 2), 11000.00)
        self.assertEqual(round(resultado.rendimento_bruto, 2), 772.86)
        self.assertEqual(round(resultado.imposto_renda, 2), 115.93)
        self.assertEqual(round(resultado.valor_final_liquido, 2), 11656.93)

    def test_periodo_sem_aporte(self):
        codigo = """
        INVESTIMENTO "CDB"
            VALOR_INICIAL 2000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        IMPRIMIR RESUMO "CDB"
        """
        tabela = executar(codigo)
        simbolo = tabela.buscar("CDB")
        self.assertEqual(simbolo.valor_inicial, 2000.00)
        self.assertEqual(simbolo.aporte, 0.0)
        self.assertEqual(simbolo.periodo, 12)

    def test_imposto_regressivo(self):
        codigo = """
        INVESTIMENTO "CurtoPrazo"
            VALOR_INICIAL 1000.00
            PERIODO 6 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM
        INVESTIMENTO "MedioPrazo"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM
        INVESTIMENTO "LongoPrazo"
            VALOR_INICIAL 1000.00
            PERIODO 36 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM
        """
        tabela = executar(codigo)
        self.assertAlmostEqual(tabela.buscar("CurtoPrazo").imposto, 0.225, places=12)
        self.assertAlmostEqual(tabela.buscar("MedioPrazo").imposto, 0.20, places=12)
        self.assertAlmostEqual(tabela.buscar("LongoPrazo").imposto, 0.15, places=12)

    def test_taxa_zero_e_consistencia_simulacao_evolucao(self):
        codigo = """
        INVESTIMENTO "SemJuros"
            VALOR_INICIAL 1000.00
            APORTE 200.00 POR 10 MESES
            TAXA 0.0 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        """
        tabela = executar(codigo)
        simbolo = tabela.buscar("SemJuros")
        resultado = Resultado(simbolo)
        self.assertEqual(resultado.total_investido, 3000.00)
        self.assertEqual(resultado.rendimento_bruto, 0.0)
        self.assertEqual(resultado.valor_final_liquido, 3000.00)

        # Verifica convergencia entre a simulacao mes a mes e a formula fechada
        tabela_ap = executar(CENARIO_APOSENTADORIA)
        sim_ap = tabela_ap.buscar("Aposentadoria")
        res_ap = Resultado(sim_ap)
        _, brutos, liquidos, investidos = Interpretador._simular_evolucao(sim_ap)
        self.assertAlmostEqual(brutos[-1], res_ap.valor_final_bruto, places=9)
        self.assertAlmostEqual(liquidos[-1], res_ap.valor_final_liquido, places=9)
        self.assertAlmostEqual(investidos[-1], res_ap.total_investido, places=9)


class TestAnaliseSemantica(unittest.TestCase):
    """Valida a deteccao de erros semanticos e restricoes de dominio."""

    def test_declaracao_duplicada(self):
        codigo = """
        INVESTIMENTO "A"
            VALOR_INICIAL 100.00
            PERIODO 12 MESES
        FIM
        INVESTIMENTO "A"
            VALOR_INICIAL 200.00
            PERIODO 12 MESES
        FIM
        """
        with self.assertRaises(DeclaracaoDuplicadaError):
            executar(codigo)

    def test_investimento_nao_declarado(self):
        codigo = 'IMPRIMIR RESUMO "Inexistente"'
        with self.assertRaises(InvestimentoNaoDeclaradoError):
            executar(codigo)

    def test_valor_fora_do_dominio(self):
        codigo = """
        INVESTIMENTO "B"
            VALOR_INICIAL 100.00
            PERIODO 12 MESES
            IMPOSTO 150.0 PORCENTO
        FIM
        """
        with self.assertRaises(ValorForaDoDominioError):
            executar(codigo)

    def test_valor_negativo_semantico(self):
        codigo = """
        INVESTIMENTO "Negativo"
            VALOR_INICIAL -500.00
            APORTE 100.00 POR 12 MESES
        FIM
        """
        with self.assertRaises(ValorForaDoDominioError):
            executar(codigo)

    def test_parametro_duplicado(self):
        codigo = """
        INVESTIMENTO "Duplicado"
            VALOR_INICIAL 1000.00
            VALOR_INICIAL 2000.00
            PERIODO 12 MESES
        FIM
        """
        with self.assertRaises(ParametroDuplicadoError):
            executar(codigo)

    def test_prazo_obrigatorio(self):
        codigo = """
        INVESTIMENTO "SemPrazo"
            VALOR_INICIAL 1000.00
            TAXA 0.8 PORCENTO AO_MES
        FIM
        """
        with self.assertRaises(ParametroObrigatorioError):
            executar(codigo)

    def test_rastreamento_linha_coluna_erro_semantico(self):
        codigo = (
            'INVESTIMENTO "TesteLinha"\n'
            "    VALOR_INICIAL 1000.00\n"
            "    PERIODO 12 MESES\n"
            "    TAXA -0.5 PORCENTO AO_MES\n"
            "FIM\n"
        )
        with self.assertRaises(ValorForaDoDominioError) as ctx:
            executar(codigo)
        self.assertEqual(ctx.exception.linha, 4)
        self.assertEqual(ctx.exception.coluna, 5)
        self.assertIn("Linha 4, Coluna 5", str(ctx.exception))

    def test_cenario_duplicado_em_comparar_grafico(self):
        codigo = """
        INVESTIMENTO "CenarioUnico"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
        FIM
        COMPARAR GRAFICO "CenarioUnico" "CenarioUnico"
        """
        with self.assertRaises(ParametroDuplicadoError):
            executar(codigo)

    def test_conflito_aporte_e_periodo(self):
        codigo = """
        INVESTIMENTO "ConflitoPrazo"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            APORTE 200.00 POR 12 MESES
        FIM
        """
        with self.assertRaises(ParametroDuplicadoError) as ctx:
            executar(codigo)
        self.assertIn("conflito de parametros", str(ctx.exception))

    def test_conflito_imposto_fixo_e_regressivo(self):
        codigo = """
        INVESTIMENTO "ConflitoImposto"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            IMPOSTO 15.0 PORCENTO
            IMPOSTO REGRESSIVO
        FIM
        """
        with self.assertRaises(ParametroDuplicadoError) as ctx:
            executar(codigo)
        self.assertIn("conflito de parametros", str(ctx.exception))

    def test_identificador_vazio_ou_espacos(self):
        codigo = """
        INVESTIMENTO "   "
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
        FIM
        """
        with self.assertRaises(ValorForaDoDominioError):
            executar(codigo)

    def test_investimento_sem_capital(self):
        codigo_sem_parametro_capital = """
        INVESTIMENTO "SemCapital"
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
        FIM
        """
        with self.assertRaises(ParametroObrigatorioError):
            executar(codigo_sem_parametro_capital)

        codigo_capital_zero = """
        INVESTIMENTO "CapitalZero"
            VALOR_INICIAL 0.00
            APORTE 0.00 POR 12 MESES
            TAXA 1.0 PORCENTO AO_MES
        FIM
        """
        with self.assertRaises(ValorForaDoDominioError):
            executar(codigo_capital_zero)

    def test_rollback_tabela_simbolos_apos_erro_semantico(self):
        analisador = AnalisadorSemantico()
        ast_invalida = analisar(
            """
            INVESTIMENTO "Incompleto"
                VALOR_INICIAL 1000.00
                TAXA -1.0 PORCENTO AO_MES
                PERIODO 12 MESES
            FIM
            """
        )
        with self.assertRaises(ValorForaDoDominioError):
            analisador.analisar(ast_invalida)
        with self.assertRaises(InvestimentoNaoDeclaradoError):
            analisador.tabela.buscar("Incompleto")


class TestGeracaoGraficos(unittest.TestCase):
    """Valida a geracao de graficos individuais e comparativos em diretorio isolado."""

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


class TestCLI(unittest.TestCase):
    """Valida a interface de linha de comando (cli.py)."""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
