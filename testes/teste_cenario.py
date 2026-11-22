"""Plano de testes da DSL Financeira.

Cenario de teste proposto no artigo (Secao IV) e validacoes semanticas.
Execucao: python -m testes.teste_cenario (a partir da raiz do projeto)
"""

import os
import sys

from lark.visitors import Interpreter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl_financeira import (  # noqa: E402
    AnalisadorSemantico,
    Interpretador,
    Resultado,
    executar,
)
from dsl_financeira.erros import (  # noqa: E402
    DeclaracaoDuplicadaError,
    InvestimentoNaoDeclaradoError,
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)

CENARIO = """
INVESTIMENTO "Aposentadoria"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 0.8 PORCENTO AO_MES
    IMPOSTO 15.0 PORCENTO
FIM

IMPRIMIR RESUMO "Aposentadoria"
"""


def teste_arquitetura_visitor_lark():
    print("--- Teste 0: heranca nativa de lark.visitors.Interpreter ---")
    assert issubclass(AnalisadorSemantico, Interpreter)
    assert issubclass(Interpretador, Interpreter)
    print("OK\n")


def teste_cenario_proposto():
    print("--- Teste 1: cenario proposto no artigo ---")
    tabela = executar(CENARIO)
    simbolo = tabela.buscar("Aposentadoria")
    assert simbolo.valor_inicial == 5000.00
    assert simbolo.aporte == 500.00
    assert simbolo.periodo == 12
    assert abs(simbolo.taxa - 0.008) < 1e-12
    assert abs(simbolo.imposto - 0.15) < 1e-12

    resultado = Resultado(simbolo)
    assert round(resultado.total_investido, 2) == 11000.00
    assert round(resultado.rendimento_bruto, 2) == 772.86
    assert round(resultado.imposto_renda, 2) == 115.93
    assert round(resultado.valor_final_liquido, 2) == 11656.93
    print("OK\n")


def teste_declaracao_duplicada():
    print("--- Teste 2: declaracao duplicada ---")
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
    try:
        executar(codigo)
    except DeclaracaoDuplicadaError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado DeclaracaoDuplicadaError")


def teste_investimento_nao_declarado():
    print("--- Teste 3: investimento nao declarado ---")
    codigo = 'IMPRIMIR RESUMO "Inexistente"'
    try:
        executar(codigo)
    except InvestimentoNaoDeclaradoError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado InvestimentoNaoDeclaradoError")


def teste_valor_fora_do_dominio():
    print("--- Teste 4: valor fora do dominio ---")
    codigo = """
    INVESTIMENTO "B"
        VALOR_INICIAL 100.00
        PERIODO 12 MESES
        IMPOSTO 150.0 PORCENTO
    FIM
    """
    try:
        executar(codigo)
    except ValorForaDoDominioError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado ValorForaDoDominioError")


def teste_gerar_grafico():
    print("--- Teste 5: geracao de grafico ---")
    codigo = """
    INVESTIMENTO "Reserva"
        VALOR_INICIAL 1000.00
        APORTE 100.00 POR 24 MESES
        TAXA 1.0 PORCENTO AO_MES
        IMPOSTO 15.0 PORCENTO
    FIM
    GERAR GRAFICO "Reserva"
    """
    executar(codigo)
    assert os.path.exists("grafico_Reserva.png")
    print("OK\n")


def teste_valor_negativo_semantico():
    print("--- Teste 6: valor negativo capturado na analise semantica ---")
    codigo = """
    INVESTIMENTO "Negativo"
        VALOR_INICIAL -500.00
        APORTE 100.00 POR 12 MESES
    FIM
    """
    try:
        executar(codigo)
    except ValorForaDoDominioError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado ValorForaDoDominioError para valor negativo")


def teste_parametro_duplicado():
    print("--- Teste 7: parametro duplicado no mesmo investimento ---")
    codigo = """
    INVESTIMENTO "Duplicado"
        VALOR_INICIAL 1000.00
        VALOR_INICIAL 2000.00
        PERIODO 12 MESES
    FIM
    """
    try:
        executar(codigo)
    except ParametroDuplicadoError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado ParametroDuplicadoError")


def teste_periodo_sem_aporte():
    print("--- Teste 8: investimento com PERIODO sem APORTE ---")
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
    assert simbolo.valor_inicial == 2000.00
    assert simbolo.aporte == 0.0
    assert simbolo.periodo == 12
    print("OK\n")


def teste_prazo_obrigatorio():
    print("--- Teste 9: investimento sem prazo definido (APORTE ou PERIODO) ---")
    codigo = """
    INVESTIMENTO "SemPrazo"
        VALOR_INICIAL 1000.00
        TAXA 0.8 PORCENTO AO_MES
    FIM
    """
    try:
        executar(codigo)
    except ParametroObrigatorioError as erro:
        print(f"OK -> {erro}\n")
        return
    raise AssertionError("Esperado ParametroObrigatorioError")


def teste_imposto_regressivo():
    print("--- Teste 10: tabela regressiva automatica de IR ---")
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
    assert abs(tabela.buscar("CurtoPrazo").imposto - 0.225) < 1e-12
    assert abs(tabela.buscar("MedioPrazo").imposto - 0.20) < 1e-12
    assert abs(tabela.buscar("LongoPrazo").imposto - 0.15) < 1e-12
    print("OK\n")


def teste_comparar_grafico():
    print("--- Teste 11: geracao de grafico comparativo entre cenarios ---")
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
    executar(codigo)
    assert os.path.exists("grafico_comparativo_CenarioA_vs_CenarioB.png")
    print("OK\n")


if __name__ == "__main__":
    teste_arquitetura_visitor_lark()
    teste_cenario_proposto()
    teste_declaracao_duplicada()
    teste_investimento_nao_declarado()
    teste_valor_fora_do_dominio()
    teste_gerar_grafico()
    teste_valor_negativo_semantico()
    teste_parametro_duplicado()
    teste_periodo_sem_aporte()
    teste_prazo_obrigatorio()
    teste_imposto_regressivo()
    teste_comparar_grafico()
    print("Todos os testes foram executados com sucesso.")
