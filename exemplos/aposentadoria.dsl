# ============================================================================
# Cenario Base de Simulacao Financeira (aposentadoria.dsl)
#
# Script de demonstracao correspondente ao estudo de caso da Secao IV-A do
# artigo IEEE, modelando uma aplicacao com aporte inicial, aportes mensais
# recorrentes por 12 meses e aliquota fixa de Imposto de Renda.
# ============================================================================

INVESTIMENTO "Aposentadoria"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 0.8 PORCENTO AO_MES
    IMPOSTO 15.0 PORCENTO
FIM

IMPRIMIR RESUMO "Aposentadoria"
