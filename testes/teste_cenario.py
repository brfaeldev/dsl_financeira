"""Suite de testes automatizados da DSL Financeira (padrao unittest).

Execucao:
    python -m unittest discover -s testes -p "teste_*.py" -v
    python -m testes.teste_cenario
"""

import os
import unittest

from lark.visitors import Interpreter

from dsl_financeira import (
    AnalisadorSemantico,
    Interpretador,
    Resultado,
    criar_parser,
    executar,
)
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


class TestGeracaoGraficos(unittest.TestCase):
    """Valida a geracao de graficos individuais e comparativos em output/."""

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
        caminho = os.path.join("output", "grafico_Reserva.png")
        executar(codigo)
        self.assertTrue(os.path.exists(caminho))
        os.remove(caminho)

    def test_sanitizacao_nome_arquivo_grafico(self):
        codigo = """
        INVESTIMENTO "CDB 110% / Liquidez: Diaria"
            VALOR_INICIAL 1000.00
            PERIODO 12 MESES
            TAXA 0.9 PORCENTO AO_MES
        FIM
        GERAR GRAFICO "CDB 110% / Liquidez: Diaria"
        """
        caminho = os.path.join("output", "grafico_CDB_110%_Liquidez_Diaria.png")
        executar(codigo)
        self.assertTrue(os.path.exists(caminho))
        os.remove(caminho)

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
        caminho = os.path.join("output", "grafico_comparativo_CenarioA_vs_CenarioB.png")
        executar(codigo)
        self.assertTrue(os.path.exists(caminho))
        os.remove(caminho)


if __name__ == "__main__":
    unittest.main(verbosity=2)
