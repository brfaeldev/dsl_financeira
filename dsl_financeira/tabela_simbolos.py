"""Tabela de Simbolos da DSL Financeira.

Para cada bloco INVESTIMENTO a tabela mantem uma estrutura contendo:
  - Identificador: nome do investimento (chave principal)
  - Atributos: valor inicial (P), aporte mensal (PMT), periodo em meses (n),
    taxa mensal (r) e aliquota de imposto (t)
"""

from .erros import DeclaracaoDuplicadaError, InvestimentoNaoDeclaradoError


class Investimento:
    """Entidade armazenada na Tabela de Simbolos."""

    def __init__(self, identificador):
        self.identificador = identificador
        self.valor_inicial = 0.0   # P
        self.aporte = 0.0          # PMT
        self.periodo = 0           # n (meses)
        self.taxa = 0.0            # r (decimal, ao mes)
        self.imposto = 0.0         # t (decimal)

    def __repr__(self):
        return (
            f"Investimento({self.identificador!r}, P={self.valor_inicial}, "
            f"PMT={self.aporte}, n={self.periodo}, r={self.taxa}, "
            f"t={self.imposto})"
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
