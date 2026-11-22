"""
Motor de Execucao e Renderizacao Grafica - AST Visitor (interpretador.py)

Percorre a AST ja validada aplicando as equacoes financeiras de juros compostos,
valor futuro de anuidades e deducoes de Imposto de Renda, emitindo resumos
formatados no terminal e graficos individuais ou comparativos via Matplotlib.

Modelo matematico aplicado:
    FV_aportes          = PMT * ((1 + r)^n - 1) / r
    FV_inicial          = P * (1 + r)^n
    Total Investido     = P + PMT * n
    Rendimento Bruto    = (FV_inicial + FV_aportes) - Total Investido
    Imposto de Renda    = Rendimento Bruto * t
    Valor Final Liquido = FV_inicial + FV_aportes - Imposto de Renda
"""

import os
import re

from lark.visitors import Interpreter

from .semantico import _texto


def _moeda(valor):
    """Formata um numero no padrao monetario brasileiro (R$ 1.234,56)."""
    texto = f"{valor:,.2f}"
    # Converte separador de milhar (',' -> '.') e decimal ('.' -> ',') usando '#' como pivo
    texto = texto.replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {texto}"


def _sanitizar_nome_arquivo(identificador):
    """Substitui espacos e caracteres invalidos de sistema de arquivos por underscore."""
    limpo = re.sub(r'[\\/:*?"<>|\s]+', "_", identificador.strip())
    return limpo.strip("_") or "investimento"


class Resultado:
    """Resultado consolidado da simulacao de um investimento (formulas fechadas)."""

    def __init__(self, simbolo):
        self.identificador = simbolo.identificador
        P = simbolo.valor_inicial
        PMT = simbolo.aporte
        n = simbolo.periodo
        r = simbolo.taxa
        t = simbolo.imposto

        # Tratamento de caso limite (taxa zero) para evitar divisao por zero na
        # formula do valor futuro da serie uniforme postecipada (anuidade).
        if r == 0:
            fv_aportes = PMT * n
        else:
            fv_aportes = PMT * (((1 + r) ** n - 1) / r)
        fv_inicial = P * ((1 + r) ** n)

        self.total_investido = P + PMT * n
        self.valor_final_bruto = fv_inicial + fv_aportes
        self.rendimento_bruto = self.valor_final_bruto - self.total_investido
        # O Imposto de Renda incide exclusivamente sobre o rendimento bruto auferido
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
        """No-op na fase de execucao: declaracoes ja foram populadas na Tabela de Simbolos."""
        return None

    # ------------------------------------------------------------------
    # Simulacao mes a mes
    # ------------------------------------------------------------------
    @staticmethod
    def _simular_evolucao(simbolo):
        """Gera as series temporais (mes 0 ate n) para plotagem das curvas patrimoniais.

        A recorrencia `saldo = saldo * (1 + r) + PMT` modela aportes postecipados
        (ao final de cada mes), convergindo exatamente para o mesmo montante da
        formula fechada da classe `Resultado` no mes `n`.
        """
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
            # Se IMPOSTO REGRESSIVO estiver ativo, a aliquota cai conforme o mes avanca
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
        # Quando GERAR GRAFICO recebe multiplos identificadores, delega para a
        # plotagem comparativa entre cenarios.
        if len(identificadores) > 1:
            return self.comparar_grafico(tree)

        identificador = identificadores[0]
        import matplotlib
        # Backend 'Agg' permite renderizar arquivos PNG sem servidor grafico/GUI
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
        nome_seguro = _sanitizar_nome_arquivo(identificador)
        nome_arquivo = f"grafico_{nome_seguro}.png"
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
            # Plota a curva liquida em linha continua e reutiliza a mesma cor
            # em linha tracejada para a curva bruta correspondente ao mesmo cenario.
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
        nomes = "_vs_".join(_sanitizar_nome_arquivo(i) for i in identificadores)
        nome_arquivo = f"grafico_comparativo_{nomes}.png"
        arquivo = os.path.join(self.diretorio_saida, nome_arquivo)
        plt.savefig(arquivo, dpi=150)
        plt.close()
        print(f"Grafico comparativo gerado em: {arquivo}")
        return arquivo
