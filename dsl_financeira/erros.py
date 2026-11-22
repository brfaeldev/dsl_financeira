"""
Hierarquia de Excecoes Semanticas (erros.py)

Define as classes de erro customizadas lancadas durante a Analise Semantica e
manipulacao da Tabela de Simbolos, enriquecidas com o rastreamento opcional de
linha e coluna do codigo-fonte (.dsl).
"""


class ErroSemantico(Exception):
    """Classe base para os erros de analise semantica da DSL.

    Centraliza a captura de erros semanticos no CLI e formata opcionalmente as
    coordenadas (linha e coluna) extraidas dos nos da AST do Lark.
    """

    def __init__(self, mensagem, linha=None, coluna=None):
        self.linha = linha
        self.coluna = coluna
        if linha is not None and coluna is not None:
            prefixo = f"(Linha {linha}, Coluna {coluna}) "
        elif linha is not None:
            prefixo = f"(Linha {linha}) "
        else:
            prefixo = ""
        super().__init__(f"{prefixo}{mensagem}")


class DeclaracaoDuplicadaError(ErroSemantico):
    """Declaracao duplicada do mesmo investimento na Tabela de Simbolos."""

    def __init__(self, identificador, linha=None, coluna=None, mensagem=None):
        texto = mensagem or (
            f"Investimento '{identificador}' ja foi declarado anteriormente."
        )
        super().__init__(texto, linha=linha, coluna=coluna)
        self.identificador = identificador


class IndiceDuplicadoError(DeclaracaoDuplicadaError):
    """Declaracao duplicada do mesmo indexador macroeconomico na Tabela de Simbolos."""

    def __init__(self, identificador, linha=None, coluna=None):
        super().__init__(
            identificador,
            linha=linha,
            coluna=coluna,
            mensagem=f"Indice '{identificador}' ja foi declarado anteriormente.",
        )


class InvestimentoNaoDeclaradoError(ErroSemantico):
    """Referencia a um investimento nao declarado (IMPRIMIR / GERAR / COMPARAR / EXPORTAR / SIMULAR)."""

    def __init__(self, identificador, linha=None, coluna=None, mensagem=None):
        texto = mensagem or f"Investimento '{identificador}' nao foi declarado."
        super().__init__(texto, linha=linha, coluna=coluna)
        self.identificador = identificador


class IndiceNaoDeclaradoError(InvestimentoNaoDeclaradoError):
    """Referencia a um indexador macroeconomico nao declarado (TAXA ... DO / INFLACAO)."""

    def __init__(self, identificador, linha=None, coluna=None):
        super().__init__(
            identificador,
            linha=linha,
            coluna=coluna,
            mensagem=f"Indice '{identificador}' nao foi declarado.",
        )


class ValorForaDoDominioError(ErroSemantico):
    """Valor numerico fora do dominio valido do parametro."""

    def __init__(self, identificador, parametro, valor, motivo, linha=None, coluna=None):
        super().__init__(
            f"Investimento '{identificador}': valor invalido em "
            f"{parametro} = {valor}. {motivo}",
            linha=linha,
            coluna=coluna,
        )
        self.identificador = identificador
        self.parametro = parametro
        self.valor = valor


class ParametroDuplicadoError(ErroSemantico):
    """Parametro declarado mais de uma vez no mesmo bloco ou comando."""

    def __init__(self, identificador, parametro, mensagem=None, linha=None, coluna=None):
        texto = mensagem or (
            f"Investimento '{identificador}': parametro '{parametro}' "
            f"declarado mais de uma vez."
        )
        super().__init__(texto, linha=linha, coluna=coluna)
        self.identificador = identificador
        self.parametro = parametro


class ParametroObrigatorioError(ErroSemantico):
    """Ausencia de parametro obrigatorio (ex.: prazo em meses) no bloco INVESTIMENTO."""

    def __init__(self, identificador, parametro, linha=None, coluna=None):
        super().__init__(
            f"Investimento '{identificador}': parametro obrigatorio ausente "
            f"({parametro}).",
            linha=linha,
            coluna=coluna,
        )
        self.identificador = identificador
        self.parametro = parametro
