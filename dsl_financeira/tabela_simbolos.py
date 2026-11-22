"""
Tabela de Simbolos e Regras Tributarias (tabela_simbolos.py)

Mantem o dicionario global de investimentos e indexadores macroeconomicos
declarados no programa, armazenando para cada identificador seus parametros
financeiros normalizados em base mensal (P, PMT, n, r, t, inflacao, custos e
eventos de fluxo de caixa) e implementando a tabela regressiva brasileira de IR.
"""

from .erros import (
    DeclaracaoDuplicadaError,
    IndiceDuplicadoError,
    IndiceNaoDeclaradoError,
    InvestimentoNaoDeclaradoError,
)


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
        # sao armazenadas ja normalizadas na forma decimal mensal (ex.: 0.8% -> 0.008).
        self.valor_inicial = 0.0          # P: capital inicial aplicado no mes 0
        self.aporte = 0.0                 # PMT: aporte recorrente ao fim de cada mes
        self.periodo = 0                  # n: horizonte temporal em meses (obrigatorio > 0)
        self.taxa = 0.0                   # r: taxa de juros compostos mensal equivalente (decimal)
        self.imposto = 0.0                # t: aliquota final de IR sobre o rendimento (decimal)
        self.imposto_regressivo = False
        self.imposto_por_safra = False    # tributacao regressiva individual por safra (tranche)
        self.imposto_come_cotas = False   # antecipacao semestral de IR (fundos de investimento)
        self.inflacao = 0.0               # i: taxa de inflacao mensal equivalente (decimal)
        self.taxa_administracao = 0.0     # taxa de administracao/custodia mensal equivalente (decimal)
        self.aportes_extras = []          # lista de tuplas (mes, valor)
        self.resgates = []                # lista de tuplas (mes, valor)

    @property
    def usa_simulacao_detalhada(self):
        """Indica se o cenario requer apuracao iterativa mes a mes no Resultado."""
        return bool(
            self.aportes_extras
            or self.resgates
            or self.taxa_administracao > 0
            or self.imposto_por_safra
            or self.imposto_come_cotas
        )

    def aliquota_para_mes(self, mes):
        """Retorna a aliquota de IR aplicavel no mes informado."""
        if self.imposto_regressivo or self.imposto_come_cotas:
            # No mes 0 (instante inicial) utiliza-se max(1, mes) para manter a faixa
            # inicial de curto prazo (22,5%) na simulacao mes a mes dos graficos.
            mes_efetivo = max(1, mes)
            if self.imposto_come_cotas and self.periodo <= 12:
                return 0.225 if mes_efetivo <= 6 else 0.20
            return aliquota_regressiva_ir(mes_efetivo)
        return self.imposto


class TabelaSimbolos:
    """Dicionario global de investimentos e indexadores declarados no programa.

    Populada durante a Analise Semantica e consultada pelo Interpretador na
    fase de execucao.
    """

    def __init__(self):
        self._simbolos = {}
        self._indices = {}

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

    def remover(self, identificador):
        """Remove um identificador da tabela (usado para rollback se a validacao do bloco falhar)."""
        self._simbolos.pop(identificador, None)

    def listar(self):
        """Retorna os investimentos declarados na ordem de insercao."""
        return list(self._simbolos.values())

    def declarar_indice(self, identificador, taxa_mensal, linha=None, coluna=None):
        """Registra um indexador macroeconomico global (ex.: CDI, SELIC, IPCA) em base mensal."""
        if identificador in self._indices:
            raise IndiceDuplicadoError(
                identificador, linha=linha, coluna=coluna
            )
        self._indices[identificador] = taxa_mensal
        return taxa_mensal

    def buscar_indice(self, identificador, linha=None, coluna=None):
        """Recupera a taxa mensal equivalente de um indexador declarado."""
        if identificador not in self._indices:
            raise IndiceNaoDeclaradoError(
                identificador, linha=linha, coluna=coluna
            )
        return self._indices[identificador]

    def listar_indices(self):
        """Retorna um dicionario com os indexadores macroeconomicos declarados."""
        return dict(self._indices)
