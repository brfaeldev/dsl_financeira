"""Engine de Execucao (Interpretador) da DSL Financeira.

Um AST Visitor le a estrutura validada, aplica os calculos de juros compostos e
deducoes fiscais, emitindo relatorios no terminal ou gerando graficos com a
biblioteca Matplotlib.

Modelo de calculo (conforme a fundamentacao teorica do trabalho):
    FV_aportes = PMT * ((1 + r)^n - 1) / r      (valor futuro de uma anuidade)
    FV_inicial = P * (1 + r)^n                  (juros compostos sobre o aporte inicial)
    Total Investido   = P + PMT * n
    Rendimento Bruto  = (FV_inicial + FV_aportes) - Total Investido
    Imposto de Renda  = Rendimento Bruto * t
    Valor Final Liquido = FV_inicial + FV_aportes - Imposto de Renda
"""

from lark import Tree

from .semantico import _texto


def _moeda(valor):
    """Formata um numero no padrao monetario brasileiro."""
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {texto}"


class Resultado:
    """Resultado consolidado da simulacao de um investimento."""

    def __init__(self, simbolo):
        self.identificador = simbolo.identificador
        P = simbolo.valor_inicial
        PMT = simbolo.aporte
        n = simbolo.periodo
        r = simbolo.taxa
        t = simbolo.imposto

        if r == 0:
            fv_aportes = PMT * n
        else:
            fv_aportes = PMT * (((1 + r) ** n - 1) / r)
        fv_inicial = P * ((1 + r) ** n)

        self.total_investido = P + PMT * n
        self.valor_final_bruto = fv_inicial + fv_aportes
        self.rendimento_bruto = self.valor_final_bruto - self.total_investido
        self.imposto_renda = self.rendimento_bruto * t
        self.valor_final_liquido = self.valor_final_bruto - self.imposto_renda


class Interpretador:
    """AST Visitor que executa as declaracoes e comandos do programa."""

    def __init__(self, tabela):
        self.tabela = tabela

    def executar(self, ast):
        for no in ast.children:
            if not isinstance(no, Tree):
                continue
            if no.data == "imprimir_resumo":
                self.imprimir_resumo(_texto(no.children[0]))
            elif no.data == "gerar_grafico":
                self.gerar_grafico(_texto(no.children[0]))

    # ------------------------------------------------------------------
    # IMPRIMIR RESUMO
    # ------------------------------------------------------------------
    def imprimir_resumo(self, identificador):
        simbolo = self.tabela.buscar(identificador)
        resultado = Resultado(simbolo)

        print(f"=== RESUMO DO INVESTIMENTO: {resultado.identificador} ===")
        print(f"Total Investido: {_moeda(resultado.total_investido)}")
        print(f"Rendimento Bruto: {_moeda(resultado.rendimento_bruto)}")
        print(f"Imposto de Renda: {_moeda(resultado.imposto_renda)}")
        print(f"Valor Final Liquido: {_moeda(resultado.valor_final_liquido)}")
        return resultado

    # ------------------------------------------------------------------
    # GERAR GRAFICO
    # ------------------------------------------------------------------
    def gerar_grafico(self, identificador):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        simbolo = self.tabela.buscar(identificador)

        meses = list(range(simbolo.periodo + 1))
        patrimonio = []
        investido = []
        saldo = simbolo.valor_inicial
        for mes in meses:
            if mes > 0:
                saldo = saldo * (1 + simbolo.taxa) + simbolo.aporte
            patrimonio.append(saldo)
            investido.append(simbolo.valor_inicial + simbolo.aporte * mes)

        plt.figure()
        plt.plot(meses, patrimonio, label="Patrimonio acumulado")
        plt.plot(meses, investido, label="Total investido")
        plt.title(f"Curva de crescimento do patrimonio: {identificador}")
        plt.xlabel("Meses")
        plt.ylabel("Valor (R$)")
        plt.legend()
        plt.grid(True)

        arquivo = f"grafico_{identificador.replace(' ', '_')}.png"
        plt.savefig(arquivo)
        plt.close()
        print(f"Grafico gerado em: {arquivo}")
        return arquivo
