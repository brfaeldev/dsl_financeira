# ============================================================================
# Arquivo de Referencia Completa da DSL Financeira (referencia_completa.dsl)
#
# Como executar este arquivo no terminal:
#     python main.py exemplos/referencia_completa.dsl
#
# Este script serve como modelo (template) demonstrando passo a passo todas as
# declaracoes, parametros e comandos aceitos pela linguagem.
# ============================================================================

# ----------------------------------------------------------------------------
# PASSO 1: Declarar Indexadores Macroeconomicos (AO_ANO ou AO_MES)
# ----------------------------------------------------------------------------
INDICE "CDI" 10.75 PORCENTO AO_ANO
INDICE "IPCA" 4.50 PORCENTO AO_ANO
INDICE "SELIC" 0.85 PORCENTO AO_MES

# ----------------------------------------------------------------------------
# PASSO 2: Declarar Cenarios de Investimento
# ----------------------------------------------------------------------------

# Modelo A: Investimento unico sem aporte mensal (usa PERIODO em MESES ou ANOS)
INVESTIMENTO "LCI_Isenta_Prazo_Fixo"
    VALOR_INICIAL 15000.00
    PERIODO 2 ANOS
    TAXA 92.0 PORCENTO DO "CDI"
    INFLACAO "IPCA"
    IMPOSTO 0.0 PORCENTO
FIM

# Modelo B: Aportes mensais + Aportes extras (13o salario) + Resgate parcial
# com Imposto Regressivo calculado individualmente por safra de aporte
INVESTIMENTO "CDB_Pos_Fixado_Com_Eventos"
    VALOR_INICIAL 10000.00
    APORTE 500.00 POR 24 MESES
    APORTE_EXTRA 2500.00 NO_MES 12
    APORTE_EXTRA 2500.00 NO_MES 24
    RESGATE 1000.00 NO_MES 18
    TAXA 110.0 PORCENTO DO "CDI"
    INFLACAO "IPCA"
    IMPOSTO REGRESSIVO POR_SAFRA
FIM

# Modelo C: Titulo hibrido (IPCA + taxa prefixada) com Taxa de Custodia/Adm
INVESTIMENTO "Tesouro_IPCA_Aposentadoria"
    VALOR_INICIAL 10000.00
    APORTE 500.00 POR 2 ANOS
    TAXA "IPCA" + 6.20 PORCENTO AO_ANO
    TAXA_ADMINISTRACAO 0.20 PORCENTO AO_ANO
    INFLACAO "IPCA"
    IMPOSTO REGRESSIVO
FIM

# Modelo D: Fundo de Investimento com taxa prefixada anual e regime Come-Cotas
INVESTIMENTO "Fundo_Renda_Fixa_ComeCotas"
    VALOR_INICIAL 10000.00
    APORTE 500.00 POR 24 MESES
    TAXA 11.50 PORCENTO AO_ANO
    TAXA_ADMINISTRACAO 0.80 PORCENTO AO_ANO
    INFLACAO 4.50 PORCENTO AO_ANO
    IMPOSTO COME_COTAS
FIM

# ----------------------------------------------------------------------------
# PASSO 3: Comandos de Resumo e Simulacao de Renda Passiva (Terminal)
# ----------------------------------------------------------------------------
IMPRIMIR RESUMO "LCI_Isenta_Prazo_Fixo"
IMPRIMIR RESUMO "CDB_Pos_Fixado_Com_Eventos"
IMPRIMIR RESUMO "Tesouro_IPCA_Aposentadoria"
IMPRIMIR RESUMO "Fundo_Renda_Fixa_ComeCotas"

# Simula por quanto tempo o patrimonio acumulado sustenta uma retirada mensal
SIMULAR RENDA "Tesouro_IPCA_Aposentadoria" RETIRADA 300.00 AO_MES

# ----------------------------------------------------------------------------
# PASSO 4: Comandos de Graficos, Exportacao de Dados e Relatorio (pasta output/)
# ----------------------------------------------------------------------------
GERAR GRAFICO "CDB_Pos_Fixado_Com_Eventos"
COMPARAR GRAFICO "LCI_Isenta_Prazo_Fixo" "CDB_Pos_Fixado_Com_Eventos" "Tesouro_IPCA_Aposentadoria" "Fundo_Renda_Fixa_ComeCotas"
GERAR GRAFICO_INTERATIVO "LCI_Isenta_Prazo_Fixo" "CDB_Pos_Fixado_Com_Eventos" "Tesouro_IPCA_Aposentadoria" "Fundo_Renda_Fixa_ComeCotas"

EXPORTAR CSV "CDB_Pos_Fixado_Com_Eventos"
EXPORTAR JSON "LCI_Isenta_Prazo_Fixo" "CDB_Pos_Fixado_Com_Eventos" "Tesouro_IPCA_Aposentadoria" "Fundo_Renda_Fixa_ComeCotas"
GERAR RELATORIO "relatorio_referencia_completa.md"
