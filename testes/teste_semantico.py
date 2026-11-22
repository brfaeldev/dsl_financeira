"""
Testes do Analisador Semantico e Tabela de Simbolos (teste_semantico.py)

Valida a deteccao de erros semanticos, restricoes de dominio numerico,
conflitos de parametros mutuamente exclusivos, rastreamento de linha e coluna,
rollback na Tabela de Simbolos e validacao de saldo disponivel em resgates.
"""

import unittest

from dsl_financeira import AnalisadorSemantico, analisar, executar
from dsl_financeira.erros import (
    DeclaracaoDuplicadaError,
    IndiceDuplicadoError,
    IndiceNaoDeclaradoError,
    InvestimentoNaoDeclaradoError,
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)


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

    def test_erros_semanticos_indices_e_eventos_fluxo_caixa(self):
        with self.assertRaises(IndiceNaoDeclaradoError):
            executar(
                """
                INVESTIMENTO "SemCDI"
                    VALOR_INICIAL 1000.00
                    PERIODO 12 MESES
                    TAXA 100.0 PORCENTO DO "CDI"
                FIM
                """
            )

        with self.assertRaises(IndiceDuplicadoError):
            executar(
                """
                INDICE "CDI" 10.0 PORCENTO AO_ANO
                INDICE "CDI" 11.0 PORCENTO AO_ANO
                """
            )

        with self.assertRaises(ValorForaDoDominioError):
            executar(
                """
                INVESTIMENTO "EventoForaDoPrazo"
                    VALOR_INICIAL 1000.00
                    PERIODO 12 MESES
                    APORTE_EXTRA 500.00 NO_MES 24
                FIM
                """
            )

        with self.assertRaises(ValorForaDoDominioError):
            executar(
                """
                INVESTIMENTO "ResgateExcessivo"
                    VALOR_INICIAL 1000.00
                    PERIODO 12 MESES
                    RESGATE 5000.00 NO_MES 6
                FIM
                """
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
