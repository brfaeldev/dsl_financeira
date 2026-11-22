"""
Testes de Arquitetura do Compilador e Front-End Sintatico (teste_arquitetura.py)

Valida a aderencia arquitetural aos padroes de projeto descritos no artigo IEEE:
heranca nativa de `lark.visitors.Interpreter`, cache em memoria do parser e
compatibilidade entre os algoritmos LALR(1) e Earley.
"""

import unittest

from lark.visitors import Interpreter

from dsl_financeira import (
    AnalisadorSemantico,
    Interpretador,
    analisar,
    criar_parser,
    executar,
)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
