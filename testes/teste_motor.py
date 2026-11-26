"""
Testes do Motor Matematico, Financeiro e Tributario (teste_motor.py)

Valida a precisao matematica das simulacoes financeiras (cenario base do artigo,
conversao de unidades anuais, inflacao e Equacao de Fisher, indexadores CDI e
IPCA+, eventos dinamicos de fluxo de caixa, taxa de administracao, come-cotas,
IR regressivo por safra e simulacao de renda passiva na aposentadoria).
"""

import contextlib
import io
import math
import unittest

from dsl_financeira import (
    AnalisadorSemantico,
    Interpretador,
    Resultado,
    analisar,
    executar,
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


class TestSimulacaoFinanceira(unittest.TestCase):
    """Valida os calculos matematicos e tributarios do motor de execucao."""

    def test_cenario_proposto_artigo(self):
        """Valida o cenario base 'Aposentadoria' (Secao IV-B do artigo IEEE)."""
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
        ultimo_mes = Interpretador.simular_detalhado(sim_ap)[-1]
        self.assertAlmostEqual(
            ultimo_mes["patrimonio_bruto"], res_ap.valor_final_bruto, places=9
        )
        self.assertAlmostEqual(
            ultimo_mes["patrimonio_liquido"], res_ap.valor_final_liquido, places=9
        )
        self.assertAlmostEqual(
            ultimo_mes["total_investido"], res_ap.total_investido, places=9
        )

    def test_unidades_anuais_ao_ano_e_anos(self):
        """Valida a conversao equivalente de juros compostos para AO_ANO e ANOS."""
        codigo = """
        INVESTIMENTO "Anual"
            VALOR_INICIAL 10000.00
            PERIODO 2 ANOS
            TAXA 12.0 PORCENTO AO_ANO
            IMPOSTO REGRESSIVO
        FIM
        """
        tabela = executar(codigo)
        simbolo = tabela.buscar("Anual")
        self.assertEqual(simbolo.periodo, 24)
        self.assertAlmostEqual(simbolo.taxa, (1.12 ** (1 / 12)) - 1, places=12)
        res = Resultado(simbolo)
        # 10000 * (1.12)^2 = 12544.00
        self.assertAlmostEqual(res.valor_final_bruto, 12544.00, places=6)

    def test_inflacao_e_rentabilidade_real(self):
        """Valida a deflacao do patrimonio liquido pelo indice de inflacao."""
        codigo = """
        INVESTIMENTO "ComInflacao"
            VALOR_INICIAL 10000.00
            PERIODO 1 ANOS
            TAXA 10.0 PORCENTO AO_ANO
            INFLACAO 4.5 PORCENTO AO_ANO
            IMPOSTO 0.0 PORCENTO
        FIM
        """
        tabela = executar(codigo)
        simbolo = tabela.buscar("ComInflacao")
        res = Resultado(simbolo)
        self.assertAlmostEqual(res.valor_final_liquido, 11000.00, places=6)
        self.assertAlmostEqual(
            res.valor_final_liquido_real, 11000.00 / 1.045, places=6
        )

    def test_indexadores_pos_fixados_cdi_e_hibrido_ipca_mais(self):
        """Valida INDICE global, TAXA % DO 'CDI', TAXA 'IPCA' + fixa e INFLACAO 'IPCA'."""
        codigo = """
        INDICE "CDI" 1.0 PORCENTO AO_MES
        INDICE "IPCA" 4.5 PORCENTO AO_ANO

        INVESTIMENTO "CDB_110_CDI"
            VALOR_INICIAL 10000.00
            PERIODO 12 MESES
            TAXA 110.0 PORCENTO DO "CDI"
            INFLACAO "IPCA"
            IMPOSTO REGRESSIVO
        FIM

        INVESTIMENTO "Tesouro_IPCA_Mais"
            VALOR_INICIAL 10000.00
            PERIODO 1 ANOS
            TAXA "IPCA" + 6.0 PORCENTO AO_ANO
            INFLACAO "IPCA"
            IMPOSTO 15.0 PORCENTO
        FIM
        """
        tabela = executar(codigo)
        cdb = tabela.buscar("CDB_110_CDI")
        self.assertAlmostEqual(cdb.taxa, 0.011, places=12)

        tesouro = tabela.buscar("Tesouro_IPCA_Mais")
        taxa_anual_composta = 1.045 * 1.06 - 1.0
        taxa_mensal_esperada = (1.0 + taxa_anual_composta) ** (1.0 / 12.0) - 1.0
        self.assertAlmostEqual(tesouro.taxa, taxa_mensal_esperada, places=12)

    def test_eventos_fluxo_caixa_aporte_extra_e_resgate(self):
        """Valida APORTE_EXTRA e RESGATE parcial ao longo do periodo."""
        codigo = """
        INVESTIMENTO "FluxoDinamico"
            VALOR_INICIAL 5000.00
            PERIODO 12 MESES
            APORTE_EXTRA 2000.00 NO_MES 6
            RESGATE 1000.00 NO_MES 10
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        """
        tabela = executar(codigo)
        simbolo = tabela.buscar("FluxoDinamico")
        res = Resultado(simbolo)
        self.assertEqual(res.total_investido, 7000.00)
        self.assertEqual(res.total_resgatado, 1000.00)
        self.assertGreater(res.valor_final_liquido, 6000.00)

        # Verifica ausencia de dupla contagem de IR de resgate no rendimento bruto
        codigo_resgate_total = """
        INVESTIMENTO "ResgateTotal"
            VALOR_INICIAL 1000.00
            PERIODO 1 MESES
            RESGATE 1100.00 NO_MES 1
            TAXA 10.0 PORCENTO AO_MES
            IMPOSTO 15.0 PORCENTO
        FIM
        """
        res_total = Resultado(executar(codigo_resgate_total).buscar("ResgateTotal"))
        self.assertAlmostEqual(res_total.rendimento_bruto, 100.00, places=6)
        self.assertAlmostEqual(res_total.imposto_renda, 15.00, places=6)
        self.assertAlmostEqual(res_total.total_resgatado_liquido, 1085.00, places=6)

    def test_taxa_administracao_come_cotas_e_ir_por_safra(self):
        """Valida TAXA_ADMINISTRACAO, IMPOSTO COME_COTAS e IMPOSTO REGRESSIVO POR_SAFRA."""
        codigo = """
        INVESTIMENTO "SafraGlobal"
            VALOR_INICIAL 1000.00
            APORTE 1000.00 POR 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO
        FIM

        INVESTIMENTO "SafraIndividual"
            VALOR_INICIAL 1000.00
            APORTE 1000.00 POR 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO REGRESSIVO POR_SAFRA
        FIM

        INVESTIMENTO "FundoComeCotas"
            VALOR_INICIAL 10000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            TAXA_ADMINISTRACAO 0.50 PORCENTO AO_ANO
            IMPOSTO COME_COTAS
        FIM
        """
        tabela = executar(codigo)
        res_global = Resultado(tabela.buscar("SafraGlobal"))
        res_safra = Resultado(tabela.buscar("SafraIndividual"))
        # Na apuracao por safra, os aportes dos ultimos 6 meses caem na faixa de 22.5%
        # (em vez de 20% do prazo total de 12 meses), gerando IR ligeiramente maior
        self.assertGreater(res_safra.imposto_renda, res_global.imposto_renda)

        res_fundo = Resultado(tabela.buscar("FundoComeCotas"))
        self.assertGreater(res_fundo.custo_administracao, 0.0)
        self.assertGreater(res_fundo.imposto_renda, 0.0)

    def test_simulacao_renda_passiva_usufruto(self):
        """Valida o comando SIMULAR RENDA para retiradas perpetuas e finitas."""
        codigo = """
        INVESTIMENTO "ReservaRenda"
            VALOR_INICIAL 100000.00
            PERIODO 12 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO 0.0 PORCENTO
        FIM
        SIMULAR RENDA "ReservaRenda" RETIRADA 500.00 AO_MES
        SIMULAR RENDA "ReservaRenda" RETIRADA 5000.00 AO_MES
        """
        ast = analisar(codigo)
        tabela = AnalisadorSemantico().analisar(ast)
        interp = Interpretador(tabela)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            res_perpetua = interp.simular_renda(ast.children[1])
            res_finita = interp.simular_renda(ast.children[2])
        self.assertTrue(res_perpetua["perpetua"])
        self.assertEqual(res_perpetua["meses_duracao"], math.inf)
        self.assertFalse(res_finita["perpetua"])
        self.assertGreater(res_finita["meses_duracao"], 20)

        # Verifica fronteira do ultimo mes quando saldo + juros do mes cobrem a retirada
        codigo_borda = """
        INVESTIMENTO "BordaUsufruto"
            VALOR_INICIAL 995.00
            PERIODO 1 MESES
            TAXA 1.0 PORCENTO AO_MES
            IMPOSTO 0.0 PORCENTO
        FIM
        """
        sim_borda = executar(codigo_borda).buscar("BordaUsufruto")
        # Patrimonio final no mes 1 = 1004.95; com +1% no 1o mes de usufruto = 1015.00 >= 1005.00
        dados_borda = Interpretador.calcular_simulacao_renda(sim_borda, 1005.00)
        self.assertEqual(dados_borda["meses_duracao"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
