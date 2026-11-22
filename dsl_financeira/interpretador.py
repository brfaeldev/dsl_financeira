"""Engine de Execucao (Interpretador) da DSL Financeira.

Um AST Visitor baseado em lark.visitors.Interpreter le a estrutura validada,
aplica os calculos de juros compostos e deducoes fiscais, emitindo relatorios
no terminal ou gerando graficos (individuais e comparativos) com a biblioteca
Matplotlib.

Modelo de calculo (conforme a fundamentacao teorica do trabalho):
    FV_aportes = PMT * ((1 + r)^n - 1) / r      (valor futuro de uma anuidade)
    FV_inicial = P * (1 + r)^n                  (juros compostos sobre o aporte inicial)
    Total Investido   = P + PMT * n
    Rendimento Bruto  = (FV_inicial + FV_aportes) - Total Investido
    Imposto de Renda  = Rendimento Bruto * t
    Valor Final Liquido = FV_inicial + FV_aportes - Imposto de Renda
"""

import os

from lark.visitors import Interpreter

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


class Interpretador(Interpreter):
    """AST Visitor (Lark Interpreter) que executa os comandos do programa."""

    def __init__(self, tabela, diretorio_saida="output"):
        super().__init__()
        self.tabela = tabela
        self.diretorio_saida = diretorio_saida

    def executar(self, ast):
        """Percorre a AST executando os nos de comando via Visitor."""
        self.visit(ast)

    def declaracao(self, tree):
        """Declaracoes ja foram processadas na fase de Analise Semantica."""
        return None

    # ------------------------------------------------------------------
    # Simulacao mes a mes
    # ------------------------------------------------------------------
    @staticmethod
    def _simular_evolucao(simbolo):
        meses = list(range(simbolo.periodo + 1))
        patrimonio_bruto = []
        patrimonio_liquido = []
        investido = []
        saldo = simbolo.valor_inicial

        for mes in meses:
            if mes > 0:
                saldo = saldo * (1 + simbolo.taxa) + simbolo.aporte
            total_investido_mes = simbolo.valor_inicial + simbolo.aporte * mes
            rendimento_mes = saldo - total_investido_mes
            aliquota = simbolo.aliquota_para_mes(mes)
            saldo_liquido = saldo - (rendimento_mes * aliquota)

            patrimonio_bruto.append(saldo)
            patrimonio_liquido.append(saldo_liquido)
            investido.append(total_investido_mes)

        return meses, patrimonio_bruto, patrimonio_liquido, investido

    # ------------------------------------------------------------------
    # IMPRIMIR RESUMO
    # ------------------------------------------------------------------
    def imprimir_resumo(self, tree):
        identificador = _texto(tree.children[0])
        simbolo = self.tabela.buscar(identificador)
        resultado = Resultado(simbolo)

        print(f"=== RESUMO DO INVESTIMENTO: {resultado.identificador} ===")
        print(f"{'Total Investido:':<21}{_moeda(resultado.total_investido)}")
        print(f"{'Rendimento Bruto:':<21}{_moeda(resultado.rendimento_bruto)}")
        print(f"{'Imposto de Renda:':<21}{_moeda(resultado.imposto_renda)}")
        print(f"{'Valor Final Liquido:':<21}{_moeda(resultado.valor_final_liquido)}")
        return resultado

    # ------------------------------------------------------------------
    # GERAR GRAFICO / COMPARAR GRAFICO
    # ------------------------------------------------------------------
    def gerar_grafico(self, tree):
        identificadores = [_texto(t) for t in tree.children]
        if len(identificadores) > 1:
            return self.comparar_grafico(tree)

        identificador = identificadores[0]
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        simbolo = self.tabela.buscar(identificador)
        meses, patrimonio_bruto, patrimonio_liquido, investido = (
            self._simular_evolucao(simbolo)
        )

        plt.figure(figsize=(8, 5))
        plt.plot(meses, patrimonio_bruto, label="Patrimonio acumulado (bruto)")
        plt.plot(meses, patrimonio_liquido, label="Patrimonio acumulado (liquido)")
        plt.plot(meses, investido, linestyle="--", label="Total investido")
        plt.title(f"Curva de crescimento do patrimonio: {identificador}")
        plt.xlabel("Meses")
        plt.ylabel("Valor (R$)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        os.makedirs(self.diretorio_saida, exist_ok=True)
        nome_arquivo = f"grafico_{identificador.replace(' ', '_')}.png"
        arquivo = os.path.join(self.diretorio_saida, nome_arquivo)
        plt.savefig(arquivo, dpi=150)
        plt.close()
        print(f"Grafico gerado em: {arquivo}")
        return arquivo

    def comparar_grafico(self, tree):
        identificadores = [_texto(t) for t in tree.children]

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(9, 5.5))
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            meses, patrimonio_bruto, patrimonio_liquido, _ = (
                self._simular_evolucao(simbolo)
            )
            linha = plt.plot(
                meses,
                patrimonio_liquido,
                linewidth=2,
                label=f"{identificador} (liquido)",
            )
            cor = linha[0].get_color()
            plt.plot(
                meses,
                patrimonio_bruto,
                linestyle="--",
                alpha=0.55,
                color=cor,
                label=f"{identificador} (bruto)",
            )

        plt.title("Analise comparativa de crescimento do patrimonio entre cenarios")
        plt.xlabel("Meses")
        plt.ylabel("Valor (R$)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        os.makedirs(self.diretorio_saida, exist_ok=True)
        nomes = "_vs_".join(i.replace(" ", "_") for i in identificadores)
        nome_arquivo = f"grafico_comparativo_{nomes}.png"
        arquivo = os.path.join(self.diretorio_saida, nome_arquivo)
        plt.savefig(arquivo, dpi=150)
        plt.close()
        print(f"Grafico comparativo gerado em: {arquivo}")
        return arquivo
