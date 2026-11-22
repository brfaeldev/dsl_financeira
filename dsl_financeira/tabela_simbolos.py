"""Tabela de Simbolos da DSL Financeira.

Para cada bloco INVESTIMENTO a tabela mantem uma estrutura contendo:
  - Identificador: nome do investimento (chave principal)
  - Atributos: valor inicial (P), aporte mensal (PMT), periodo em meses (n),
    taxa mensal (r) e aliquota de imposto (t)
"""

from .erros import DeclaracaoDuplicadaError, InvestimentoNaoDeclaradoError


def aliquota_regressiva_ir(meses):
    """Retorna a aliquota da tabela regressiva brasileira de IR (Renda Fixa).

    - Ate 6 meses (ate 180 dias): 22,5%
    - De 7 a 12 meses (181 a 360 dias): 20,0%
    - De 13 a 24 meses (361 a 720 dias): 17,5%
    - Acima de 24 meses (> 720 dias): 15,0%
    """
    if meses <= 6:
        return 0.225
    if meses <= 12:
        return 0.20
    if meses <= 24:
        return 0.175
    return 0.15


class Investimento:
    """Entidade armazenada na Tabela de Simbolos."""

    def __init__(self, identificador):
        self.identificador = identificador
        # Atributos financeiros inicializados com valores neutros; taxas e aliquotas
        # sao armazenadas ja normalizadas na forma decimal (ex.: 0.8% -> 0.008).
        self.valor_inicial = 0.0        # P: capital inicial aplicado no mes 0
        self.aporte = 0.0               # PMT: aporte recorrente ao fim de cada mes
        self.periodo = 0                # n: horizonte temporal em meses (obrigatorio > 0)
        self.taxa = 0.0                 # r: taxa de juros compostos mensal (decimal)
        self.imposto = 0.0              # t: aliquota final de IR sobre o rendimento (decimal)
        self.imposto_regressivo = False

    def aliquota_para_mes(self, mes):
        """Retorna a aliquota de IR aplicavel no mes informado."""
        if self.imposto_regressivo:
            # No mes 0 (instante inicial) utiliza-se max(1, mes) para manter a faixa
            # inicial de curto prazo (22,5%) na simulacao mes a mes dos graficos.
            return aliquota_regressiva_ir(max(1, mes))
        return self.imposto


class TabelaSimbolos:
    """Dicionario global de investimentos declarados no programa.

    Populada durante a Analise Semantica e consultada pelo Interpretador na
    fase de execucao.
    """

    def __init__(self):
        self._simbolos = {}

    def declarar(self, identificador, linha=None, coluna=None):
        """Registra um novo identificador de investimento, impedindo redeclaracoes."""
        if identificador in self._simbolos:
            raise DeclaracaoDuplicadaError(
                identificador, linha=linha, coluna=coluna
            )
        simbolo = Investimento(identificador)
        self._simbolos[identificador] = simbolo
        return simbolo

    def buscar(self, identificador, linha=None, coluna=None):
        """Recupera um investimento ja declarado ou lanca erro de simbolo inexistente."""
        if identificador not in self._simbolos:
            raise InvestimentoNaoDeclaradoError(
                identificador, linha=linha, coluna=coluna
            )
        return self._simbolos[identificador]
