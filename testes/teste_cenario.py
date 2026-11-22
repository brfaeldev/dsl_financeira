"""Plano de testes da DSL Financeira.

Cenario de teste proposto no artigo (Secao IV) e validacoes semanticas.
Execucao: python -m testes.teste_cenario (a partir da raiz do projeto)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsl_financeira import executar  # noqa: E402
from dsl_financeira.erros import (  # noqa: E402
    DeclaracaoDuplicadaError,
    InvestimentoNaoDeclaradoError,
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


def teste_cenario_proposto():
    print("--- Teste 1: cenario proposto no artigo ---")
    tabela = executar(CENARIO)
    simbolo = tabela.buscar("Aposentadoria")
    assert simbolo.valor_inicial == 5000.00
    assert simbolo.aporte == 500.00
    assert simbolo.periodo == 12
    assert abs(simbolo.taxa - 0.008) < 1e-12
    assert abs(simbolo.imposto - 0.15) < 1e-12
    print("OK\n")


def teste_declaracao_duplicada():
    print("--- Teste 2: declaracao duplicada ---")
    codigo = """
    INVESTIMENTO "A"
        VALOR_INICIAL 100.00
    FIM
    INVESTIMENTO "A"
        VALOR_INICIAL 200.00
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
    print("OK\n")


if __name__ == "__main__":
    teste_cenario_proposto()
    teste_declaracao_duplicada()
    teste_investimento_nao_declarado()
    teste_valor_fora_do_dominio()
    teste_gerar_grafico()
    print("Todos os testes foram executados.")
