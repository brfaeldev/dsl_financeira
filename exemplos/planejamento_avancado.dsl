# ============================================================================
# Planejamento Financeiro Avancado (planejamento_avancado.dsl)
#
# Demonstra as evolucoes da DSL Financeira:
# - Indexadores macroeconomicos globais (CDI e IPCA)
# - Conversao automatica de taxas anuais (AO_ANO) e prazos em anos (ANOS)
# - Taxas pos-fixadas (% DO "CDI") e hibridas ("IPCA" + cupom prefixado)
# - Deflacao pela Equacao de Fisher (INFLACAO) e poder de compra real
# - Eventos dinamicos de fluxo de caixa (APORTE_EXTRA e RESGATE)
# - Taxa de administracao/custodia (TAXA_ADMINISTRACAO)
# - Tributacao regressiva por safra de aporte (POR_SAFRA) e Come-Cotas
# - Simulacao de fase de usufruto (SIMULAR RENDA)
# - Exportacao CSV/JSON, grafico interativo HTML e relatorio consolidado (.md)
# ============================================================================

INDICE "CDI" 10.75 PORCENTO AO_ANO
INDICE "IPCA" 4.50 PORCENTO AO_ANO

INVESTIMENTO "CDB_110_CDI_Safra"
    VALOR_INICIAL 10000.00
    APORTE 1000.00 POR 2 ANOS
    APORTE_EXTRA 3000.00 NO_MES 12
    RESGATE 1500.00 NO_MES 18
    TAXA 110.0 PORCENTO DO "CDI"
    INFLACAO "IPCA"
    IMPOSTO REGRESSIVO POR_SAFRA
FIM

INVESTIMENTO "Tesouro_IPCA_Mais"
    VALOR_INICIAL 10000.00
    APORTE 1000.00 POR 2 ANOS
    TAXA "IPCA" + 6.0 PORCENTO AO_ANO
    TAXA_ADMINISTRACAO 0.20 PORCENTO AO_ANO
    INFLACAO "IPCA"
    IMPOSTO REGRESSIVO
FIM

INVESTIMENTO "Fundo_Multimercado_ComeCotas"
    VALOR_INICIAL 10000.00
    APORTE 1000.00 POR 24 MESES
    TAXA 11.80 PORCENTO AO_ANO
    TAXA_ADMINISTRACAO 1.00 PORCENTO AO_ANO
    INFLACAO 4.50 PORCENTO AO_ANO
    IMPOSTO COME_COTAS
FIM

IMPRIMIR RESUMO "CDB_110_CDI_Safra"
IMPRIMIR RESUMO "Tesouro_IPCA_Mais"
IMPRIMIR RESUMO "Fundo_Multimercado_ComeCotas"

SIMULAR RENDA "Tesouro_IPCA_Mais" RETIRADA 250.00 AO_MES

COMPARAR GRAFICO "CDB_110_CDI_Safra" "Tesouro_IPCA_Mais" "Fundo_Multimercado_ComeCotas"
GERAR GRAFICO_INTERATIVO "CDB_110_CDI_Safra" "Tesouro_IPCA_Mais" "Fundo_Multimercado_ComeCotas"
EXPORTAR CSV "CDB_110_CDI_Safra"
EXPORTAR JSON "CDB_110_CDI_Safra" "Tesouro_IPCA_Mais" "Fundo_Multimercado_ComeCotas"
GERAR RELATORIO "relatorio_simulacao.md"
