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
        self.valor_inicial = 0.0        # P
        self.aporte = 0.0               # PMT
        self.periodo = 0                # n (meses)
        self.taxa = 0.0                 # r (decimal, ao mes)
        self.imposto = 0.0              # t (decimal)
        self.imposto_regressivo = False

    def aliquota_para_mes(self, mes):
        """Retorna a aliquota de IR aplicavel no mes informado."""
        if self.imposto_regressivo:
            return aliquota_regressiva_ir(max(1, mes))
        return self.imposto

    def __repr__(self):
        return (
            f"Investimento({self.identificador!r}, P={self.valor_inicial}, "
            f"PMT={self.aporte}, n={self.periodo}, r={self.taxa}, "
            f"t={self.imposto}, regressivo={self.imposto_regressivo})"
        )


class TabelaSimbolos:
    """Dicionario global de investimentos declarados no programa."""

    def __init__(self):
        self._simbolos = {}

    def declarar(self, identificador):
        if identificador in self._simbolos:
            raise DeclaracaoDuplicadaError(identificador)
        simbolo = Investimento(identificador)
        self._simbolos[identificador] = simbolo
        return simbolo

    def buscar(self, identificador):
        if identificador not in self._simbolos:
            raise InvestimentoNaoDeclaradoError(identificador)
        return self._simbolos[identificador]

    def existe(self, identificador):
        return identificador in self._simbolos

    def itens(self):
        return self._simbolos.items()

    def __len__(self):
        return len(self._simbolos)
