# ============================================================================
# Analise Comparativa entre Multiplos Cenarios (comparacao_cenarios.dsl)
#
# Script de demonstracao da Secao IV-B do artigo IEEE que compara tres opcoes
# de investimento com o mesmo fluxo de desembolso sob diferentes taxas e
# regimes tributarios (aliquota fixa, tabela regressiva de IR e isencao fiscal).
# ============================================================================

INVESTIMENTO "Aposentadoria"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 0.8 PORCENTO AO_MES
    IMPOSTO 15.0 PORCENTO
FIM

INVESTIMENTO "CDB_Pos_Fixado"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 1.05 PORCENTO AO_MES
    IMPOSTO REGRESSIVO
FIM

INVESTIMENTO "LCI_Isenta"
    VALOR_INICIAL 5000.00
    APORTE 500.00 POR 12 MESES
    TAXA 0.88 PORCENTO AO_MES
    IMPOSTO 0.0 PORCENTO
FIM

IMPRIMIR RESUMO "Aposentadoria"
IMPRIMIR RESUMO "CDB_Pos_Fixado"
IMPRIMIR RESUMO "LCI_Isenta"

GERAR GRAFICO "Aposentadoria"
COMPARAR GRAFICO "Aposentadoria" "CDB_Pos_Fixado" "LCI_Isenta"
