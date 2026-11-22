"""Excecoes customizadas lancadas pelo modulo semantico da DSL Financeira."""


class ErroSemantico(Exception):
    """Classe base para os erros de analise semantica da DSL."""


class DeclaracaoDuplicadaError(ErroSemantico):
    """Declaracao duplicada do mesmo investimento na Tabela de Simbolos."""

    def __init__(self, identificador):
        super().__init__(
            f"Investimento '{identificador}' ja foi declarado anteriormente."
        )
        self.identificador = identificador


class InvestimentoNaoDeclaradoError(ErroSemantico):
    """Referencia a um investimento nao declarado (IMPRIMIR / GERAR)."""

    def __init__(self, identificador):
        super().__init__(
            f"Investimento '{identificador}' nao foi declarado."
        )
        self.identificador = identificador


class ValorForaDoDominioError(ErroSemantico):
    """Valor numerico fora do dominio valido do parametro."""

    def __init__(self, identificador, parametro, valor, motivo):
        super().__init__(
            f"Investimento '{identificador}': valor invalido em "
            f"{parametro} = {valor}. {motivo}"
        )
        self.identificador = identificador
        self.parametro = parametro
        self.valor = valor
