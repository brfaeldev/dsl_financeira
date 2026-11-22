"""
Motor de Execucao, Exportacao e Renderizacao Grafica - AST Visitor (interpretador.py)

Percorre a AST ja validada aplicando as equacoes financeiras de juros compostos,
valor futuro de anuidades, eventos dinamicos de fluxo de caixa (aportes extras e
resgates), custos de administracao, deflacao pela Equacao de Fisher e regimes
tributarios (fixo, regressivo, regressivo por safra/tranches e come-cotas),
emitindo resumos no terminal, graficos PNG/HTML, exportacoes CSV/JSON,
relatorios consolidados em Markdown e simulacoes de usufruto (renda passiva).
"""

import csv
import json
import math
import os
import re
import sys

from lark.visitors import Interpreter

from .semantico import _texto
from .tabela_simbolos import aliquota_regressiva_ir


def _carregar_pyplot():
    """Importa matplotlib.pyplot garantindo o backend headless 'Agg'."""
    if "matplotlib.pyplot" not in sys.modules:
        import matplotlib
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


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


def _simular_serie_detalhada(simbolo):
    """Executa a simulacao mes a mes (0..n) contemplando todas as regras do dominio.

    Suporta:
    - Aporte inicial (P), aportes mensais recorrentes (PMT) e APORTE_EXTRA por mes;
    - RESGATE parcial por mes (consumindo proporcionalmente capital e rendimento);
    - TAXA_ADMINISTRACAO descontada mensalmente sobre o patrimonio;
    - Tributacao fixa, regressiva global, regressiva por safra (tranches) e come-cotas;
    - Deflacao do patrimonio liquido pelo fator acumulado de INFLACAO.
    """
    n = simbolo.periodo
    r = simbolo.taxa
    r_adm = simbolo.taxa_administracao
    fator_crescimento = (1.0 + r) * (1.0 - r_adm)

    extras_por_mes = {}
    for mes_e, val_e in simbolo.aportes_extras:
        extras_por_mes[mes_e] = extras_por_mes.get(mes_e, 0.0) + val_e

    resgates_por_mes = {}
    for mes_r, val_r in simbolo.resgates:
        resgates_por_mes[mes_r] = resgates_por_mes.get(mes_r, 0.0) + val_r

    # Cada safra (tranche) armazena: [mes_origem, capital_base, saldo_atual]
    safras = []
    if simbolo.valor_inicial > 0:
        safras.append([0, simbolo.valor_inicial, simbolo.valor_inicial])

    total_investido_acumulado = simbolo.valor_inicial
    total_resgatado_bruto = 0.0
    total_resgatado_liquido = 0.0
    ir_pago_acumulado = 0.0
    custo_adm_acumulado = 0.0

    # Aliquota semestral de come-cotas (20% para fundos de curto prazo <= 12m, 15% longo prazo)
    aliquota_come_cotas = 0.20 if n <= 12 else 0.15

    registros = []

    for mes in range(n + 1):
        if mes > 0:
            # 1. Rendimento bruto e deducao da taxa de administracao em cada safra
            for safra in safras:
                saldo_antes = safra[2]
                saldo_apos_juros = saldo_antes * (1.0 + r)
                custo_safra = saldo_apos_juros * r_adm
                custo_adm_acumulado += custo_safra
                safra[2] = saldo_apos_juros - custo_safra

            # 2. Aporte mensal recorrente + aporte extra agendado para o mes
            aporte_mes = simbolo.aporte + extras_por_mes.get(mes, 0.0)
            if aporte_mes > 0:
                safras.append([mes, aporte_mes, aporte_mes])
                total_investido_acumulado += aporte_mes

            # 3. Resgates parciais no mes (FIFO sobre as safras mais antigas)
            valor_resgate = resgates_por_mes.get(mes, 0.0)
            if valor_resgate > 0:
                restante = valor_resgate
                ir_resgate = 0.0
                novas_safras = []
                for safra in safras:
                    if restante <= 1e-12 or safra[2] <= 1e-12:
                        novas_safras.append(safra)
                        continue
                    retirado = min(restante, safra[2])
                    proporcao = retirado / safra[2]
                    capital_consumido = safra[1] * proporcao
                    rendimento_consumido = max(0.0, retirado - capital_consumido)

                    prazo_safra = max(1, mes - safra[0])
                    if simbolo.imposto_por_safra:
                        aliq_r = aliquota_regressiva_ir(prazo_safra)
                    else:
                        aliq_r = simbolo.aliquota_para_mes(mes)

                    ir_resgate += rendimento_consumido * aliq_r
                    safra[1] -= capital_consumido
                    safra[2] -= retirado
                    restante -= retirado
                    if safra[2] > 1e-12:
                        novas_safras.append(safra)
                safras = novas_safras
                ir_pago_acumulado += ir_resgate
                total_resgatado_bruto += valor_resgate
                total_resgatado_liquido += valor_resgate - ir_resgate

            # 4. Regime Come-Cotas semestral (meses 6, 12, 18, ...)
            if simbolo.imposto_come_cotas and mes % 6 == 0:
                for safra in safras:
                    rend_safra = max(0.0, safra[2] - safra[1])
                    if rend_safra > 0:
                        ir_cc = rend_safra * aliquota_come_cotas
                        safra[2] -= ir_cc
                        # Apos a antecipacao semestral, o novo saldo passa a ser a base ja tributada
                        safra[1] = safra[2]
                        ir_pago_acumulado += ir_cc

        saldo_bruto = sum(s[2] for s in safras)
        capital_remanescente = sum(s[1] for s in safras)
        rendimento_latente = max(0.0, saldo_bruto - capital_remanescente)

        # 5. Calculo do Imposto de Renda latente (caso resgatado no mes atual)
        if simbolo.imposto_por_safra:
            ir_latente = 0.0
            for mes_orig, cap_s, sal_s in safras:
                rend_s = max(0.0, sal_s - cap_s)
                prazo_s = max(1, mes - mes_orig)
                ir_latente += rend_s * aliquota_regressiva_ir(prazo_s)
            aliquota_efetiva = (
                ir_latente / rendimento_latente
                if rendimento_latente > 1e-12
                else simbolo.aliquota_para_mes(mes)
            )
        elif simbolo.imposto_come_cotas:
            aliquota_efetiva = aliquota_come_cotas
            ir_latente = rendimento_latente * aliquota_efetiva
        else:
            aliquota_efetiva = simbolo.aliquota_para_mes(mes)
            ir_latente = rendimento_latente * aliquota_efetiva

        saldo_liquido = saldo_bruto - ir_latente
        fator_inflacao = (1.0 + simbolo.inflacao) ** mes
        saldo_liquido_real = saldo_liquido / fator_inflacao

        # Rendimento bruto total gerado ate o mes (incluindo resgates e IR ja recolhido em come-cotas)
        rendimento_bruto_total = (
            saldo_bruto
            + total_resgatado_bruto
            + ir_pago_acumulado
            - total_investido_acumulado
        )
        imposto_total_ate_mes = ir_pago_acumulado + ir_latente

        registros.append(
            {
                "mes": mes,
                "total_investido": total_investido_acumulado,
                "patrimonio_bruto": saldo_bruto,
                "rendimento_bruto": rendimento_bruto_total,
                "aliquota_ir": aliquota_efetiva,
                "imposto_renda": imposto_total_ate_mes,
                "patrimonio_liquido": saldo_liquido,
                "patrimonio_liquido_real": saldo_liquido_real,
                "total_resgatado_bruto": total_resgatado_bruto,
                "total_resgatado_liquido": total_resgatado_liquido,
                "custo_administracao": custo_adm_acumulado,
            }
        )

    return registros


class Resultado:
    """Resultado consolidado da simulacao de um investimento."""

    def __init__(self, simbolo):
        self.identificador = simbolo.identificador
        P = simbolo.valor_inicial
        PMT = simbolo.aporte
        n = simbolo.periodo
        r = simbolo.taxa
        t = simbolo.imposto

        self.total_resgatado = 0.0
        self.custo_administracao = 0.0

        if not simbolo.usa_simulacao_detalhada:
            # Formulas fechadas classicas (Secao II-B do artigo IEEE)
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
        else:
            # Motor iterativo mes a mes para fluxos dinamicos, taxas de adm, safras e come-cotas
            ultimo = _simular_serie_detalhada(simbolo)[-1]
            self.total_investido = ultimo["total_investido"]
            self.valor_final_bruto = ultimo["patrimonio_bruto"]
            self.rendimento_bruto = ultimo["rendimento_bruto"]
            self.imposto_renda = ultimo["imposto_renda"]
            self.valor_final_liquido = ultimo["patrimonio_liquido"]
            self.total_resgatado = ultimo["total_resgatado_bruto"]
            self.custo_administracao = ultimo["custo_administracao"]

        # Deflacao pelo indice de inflacao acumulado no periodo: V_real = V_nominal / (1 + i)^n
        fator_inflacao = (1.0 + simbolo.inflacao) ** n
        self.valor_final_liquido_real = self.valor_final_liquido / fator_inflacao
        self.rendimento_liquido_real = (
            self.valor_final_liquido_real + self.total_resgatado - self.total_investido
        )
        # Taxa real mensal equivalente pela Equacao de Fisher: (1 + r_nom)/(1 + i) - 1
        self.taxa_real_mensal = (
            ((1.0 + r) / (1.0 + simbolo.inflacao)) - 1.0
            if simbolo.inflacao > 0
            else r
        )


class Interpretador(Interpreter):
    """AST Visitor (Lark Interpreter) que executa os comandos do programa."""

    def __init__(self, tabela, diretorio_saida="output"):
        super().__init__()
        self.tabela = tabela
        self.diretorio_saida = diretorio_saida
        # Mapeia (nome_arquivo -> chave_origem) para evitar que identificadores
        # distintos com a mesma forma sanitizada sobrescrevam silenciosamente arquivos.
        self._arquivos_registrados = {}
        self.artefatos_gerados = []

    def executar(self, ast):
        """Percorre a AST executando os nos de comando via Visitor."""
        self.visit(ast)

    def declaracao_indice(self, tree):
        """No-op na fase de execucao: indexadores ja foram populados na Tabela de Simbolos."""
        return None

    def declaracao(self, tree):
        """No-op na fase de execucao: declaracoes ja foram populadas na Tabela de Simbolos."""
        return None

    # ------------------------------------------------------------------
    # Simulacao mes a mes
    # ------------------------------------------------------------------
    @staticmethod
    def _simular_evolucao(simbolo):
        """Gera as series temporais (mes 0 ate n) para plotagem das curvas patrimoniais.

        Mantem a assinatura de retorno de 4 listas `(meses, patrimonio_bruto,
        patrimonio_liquido, investido)` para total compatibilidade com a API e testes.
        """
        registros = _simular_serie_detalhada(simbolo)
        meses = [reg["mes"] for reg in registros]
        patrimonio_bruto = [reg["patrimonio_bruto"] for reg in registros]
        patrimonio_liquido = [reg["patrimonio_liquido"] for reg in registros]
        investido = [reg["total_investido"] for reg in registros]
        return meses, patrimonio_bruto, patrimonio_liquido, investido

    @staticmethod
    def simular_detalhado(simbolo):
        """Retorna a lista completa de dicionarios mensais (0..n) do investimento."""
        return _simular_serie_detalhada(simbolo)

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
        if resultado.total_resgatado > 0:
            print(f"{'Total Resgatado:':<21}{_moeda(resultado.total_resgatado)}")
        if simbolo.inflacao > 0:
            print(
                f"{'Valor Liquido Real:':<21}"
                f"{_moeda(resultado.valor_final_liquido_real)}"
            )
        return resultado

    # ------------------------------------------------------------------
    # Utilitarios de Arquivos de Saida
    # ------------------------------------------------------------------
    def _resolver_caminho_saida(
        self, prefixo, sufixo_base, chave_origem, extensao="png"
    ):
        """Resolve o caminho do arquivo de saida prevenindo colisao entre identificadores distintos."""
        os.makedirs(self.diretorio_saida, exist_ok=True)
        nome_arquivo = f"{prefixo}_{sufixo_base}.{extensao}"
        contador = 2
        while (
            nome_arquivo in self._arquivos_registrados
            and self._arquivos_registrados[nome_arquivo] != chave_origem
        ):
            nome_arquivo = f"{prefixo}_{sufixo_base}_{contador}.{extensao}"
            contador += 1
        self._arquivos_registrados[nome_arquivo] = chave_origem
        caminho = os.path.join(self.diretorio_saida, nome_arquivo)
        if caminho not in self.artefatos_gerados:
            self.artefatos_gerados.append(caminho)
        return caminho

    @staticmethod
    def _finalizar_e_salvar_figura(plt, fig, ax, titulo, caminho_arquivo):
        """Aplica formatacao padrao aos eixos, salva a figura em disco e libera memoria."""
        try:
            ax.set_title(titulo)
            ax.set_xlabel("Meses")
            ax.set_ylabel("Valor (R$)")
            ax.legend()
            ax.grid(True)
            fig.tight_layout()
            fig.savefig(caminho_arquivo, dpi=150)
        finally:
            plt.close(fig)

    # ------------------------------------------------------------------
    # GERAR GRAFICO / COMPARAR GRAFICO (Matplotlib PNG)
    # ------------------------------------------------------------------
    def gerar_grafico(self, tree):
        identificadores = [_texto(t) for t in tree.children]
        if len(identificadores) > 1:
            return self.comparar_grafico(tree)

        identificador = identificadores[0]
        simbolo = self.tabela.buscar(identificador)
        registros = _simular_serie_detalhada(simbolo)
        meses = [r["mes"] for r in registros]
        patrimonio_bruto = [r["patrimonio_bruto"] for r in registros]
        patrimonio_liquido = [r["patrimonio_liquido"] for r in registros]
        investido = [r["total_investido"] for r in registros]

        plt = _carregar_pyplot()
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(meses, patrimonio_bruto, label="Patrimonio acumulado (bruto)")
        ax.plot(meses, patrimonio_liquido, label="Patrimonio acumulado (liquido)")
        if simbolo.inflacao > 0:
            patrimonio_real = [r["patrimonio_liquido_real"] for r in registros]
            ax.plot(
                meses,
                patrimonio_real,
                linestyle="-.",
                label="Patrimonio liquido real (poder de compra)",
            )
        ax.plot(meses, investido, linestyle="--", label="Total investido")

        nome_seguro = _sanitizar_nome_arquivo(identificador)
        arquivo = self._resolver_caminho_saida(
            "grafico", nome_seguro, chave_origem=("individual", identificador)
        )
        self._finalizar_e_salvar_figura(
            plt,
            fig,
            ax,
            f"Curva de crescimento do patrimonio: {identificador}",
            arquivo,
        )
        print(f"Grafico gerado em: {arquivo}")
        return arquivo

    def comparar_grafico(self, tree):
        identificadores = [_texto(t) for t in tree.children]

        plt = _carregar_pyplot()
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            registros = _simular_serie_detalhada(simbolo)
            meses = [r["mes"] for r in registros]
            patrimonio_bruto = [r["patrimonio_bruto"] for r in registros]
            patrimonio_liquido = [r["patrimonio_liquido"] for r in registros]

            linha = ax.plot(
                meses,
                patrimonio_liquido,
                linewidth=2,
                label=f"{identificador} (liquido)",
            )
            cor = linha[0].get_color()
            ax.plot(
                meses,
                patrimonio_bruto,
                linestyle="--",
                alpha=0.55,
                color=cor,
                label=f"{identificador} (bruto)",
            )
            if simbolo.inflacao > 0:
                patrimonio_real = [r["patrimonio_liquido_real"] for r in registros]
                ax.plot(
                    meses,
                    patrimonio_real,
                    linestyle=":",
                    alpha=0.85,
                    color=cor,
                    label=f"{identificador} (liquido real)",
                )

        nomes = "_vs_".join(_sanitizar_nome_arquivo(i) for i in identificadores)
        arquivo = self._resolver_caminho_saida(
            "grafico_comparativo",
            nomes,
            chave_origem=("comparativo", tuple(identificadores)),
        )
        self._finalizar_e_salvar_figura(
            plt,
            fig,
            ax,
            "Analise comparativa de crescimento do patrimonio entre cenarios",
            arquivo,
        )
        print(f"Grafico comparativo gerado em: {arquivo}")
        return arquivo

    # ------------------------------------------------------------------
    # GERAR GRAFICO_INTERATIVO (HTML Interativo com Plotly)
    # ------------------------------------------------------------------
    def gerar_grafico_interativo(self, tree):
        identificadores = [_texto(t) for t in tree.children]
        traces = []
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            registros = _simular_serie_detalhada(simbolo)
            meses = [r["mes"] for r in registros]
            traces.append(
                {
                    "x": meses,
                    "y": [round(r["patrimonio_liquido"], 2) for r in registros],
                    "mode": "lines+markers",
                    "name": f"{identificador} (Liquido)",
                }
            )
            traces.append(
                {
                    "x": meses,
                    "y": [round(r["patrimonio_bruto"], 2) for r in registros],
                    "mode": "lines",
                    "line": {"dash": "dash"},
                    "name": f"{identificador} (Bruto)",
                }
            )
            if simbolo.inflacao > 0:
                traces.append(
                    {
                        "x": meses,
                        "y": [
                            round(r["patrimonio_liquido_real"], 2) for r in registros
                        ],
                        "mode": "lines",
                        "line": {"dash": "dot"},
                        "name": f"{identificador} (Liquido Real)",
                    }
                )
            if len(identificadores) == 1:
                traces.append(
                    {
                        "x": meses,
                        "y": [round(r["total_investido"], 2) for r in registros],
                        "mode": "lines",
                        "line": {"dash": "dashdot"},
                        "name": "Total Investido",
                    }
                )

        if len(identificadores) == 1:
            sufixo = _sanitizar_nome_arquivo(identificadores[0])
            prefixo = "grafico_interativo"
            titulo = f"Evolucao Interativa do Patrimonio: {identificadores[0]}"
        else:
            sufixo = "_vs_".join(_sanitizar_nome_arquivo(i) for i in identificadores)
            prefixo = "grafico_interativo_comparativo"
            titulo = "Analise Comparativa Interativa entre Cenarios"

        arquivo = self._resolver_caminho_saida(
            prefixo,
            sufixo,
            chave_origem=("html_interativo", tuple(identificadores)),
            extensao="html",
        )

        layout = {
            "title": titulo,
            "xaxis": {"title": "Meses"},
            "yaxis": {"title": "Valor (R$)", "tickprefix": "R$ "},
            "hovermode": "x unified",
            "template": "plotly_white",
        }
        conteudo_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>{titulo}</title>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 24px; background: #f8fafc; }}
        #grafico {{ width: 100%; max-width: 1100px; height: 600px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    </style>
</head>
<body>
    <div id="grafico"></div>
    <script>
        const traces = {json.dumps(traces, ensure_ascii=False)};
        const layout = {json.dumps(layout, ensure_ascii=False)};
        Plotly.newPlot('grafico', traces, layout, {{responsive: true}});
    </script>
</body>
</html>
"""
        with open(arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo_html)
        print(f"Grafico interativo gerado em: {arquivo}")
        return arquivo

    # ------------------------------------------------------------------
    # EXPORTAR CSV / EXPORTAR JSON
    # ------------------------------------------------------------------
    def exportar_csv(self, tree):
        identificadores = [_texto(t) for t in tree.children]
        arquivos = []
        campos = [
            "mes",
            "total_investido",
            "patrimonio_bruto",
            "rendimento_bruto",
            "aliquota_ir",
            "imposto_renda",
            "patrimonio_liquido",
            "patrimonio_liquido_real",
        ]
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            registros = _simular_serie_detalhada(simbolo)
            nome_seguro = _sanitizar_nome_arquivo(identificador)
            arquivo = self._resolver_caminho_saida(
                "evolucao",
                nome_seguro,
                chave_origem=("csv", identificador),
                extensao="csv",
            )
            with open(arquivo, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(campos)
                for reg in registros:
                    writer.writerow([f"{reg[c]:.2f}" if c != "mes" and c != "aliquota_ir" else (reg[c] if c == "mes" else f"{reg[c]:.4f}") for c in campos])
            print(f"CSV exportado em: {arquivo}")
            arquivos.append(arquivo)
        return arquivos[0] if len(arquivos) == 1 else arquivos

    def exportar_json(self, tree):
        identificadores = [_texto(t) for t in tree.children]
        payload = {"investimentos": []}
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            resultado = Resultado(simbolo)
            registros = _simular_serie_detalhada(simbolo)
            payload["investimentos"].append(
                {
                    "identificador": identificador,
                    "parametros": {
                        "valor_inicial": simbolo.valor_inicial,
                        "aporte_mensal": simbolo.aporte,
                        "periodo_meses": simbolo.periodo,
                        "taxa_mensal": simbolo.taxa,
                        "inflacao_mensal": simbolo.inflacao,
                        "taxa_administracao_mensal": simbolo.taxa_administracao,
                        "aliquota_ir_final": simbolo.imposto,
                        "imposto_regressivo": simbolo.imposto_regressivo,
                        "imposto_por_safra": simbolo.imposto_por_safra,
                        "imposto_come_cotas": simbolo.imposto_come_cotas,
                    },
                    "resumo": {
                        "total_investido": round(resultado.total_investido, 2),
                        "valor_final_bruto": round(resultado.valor_final_bruto, 2),
                        "rendimento_bruto": round(resultado.rendimento_bruto, 2),
                        "imposto_renda": round(resultado.imposto_renda, 2),
                        "valor_final_liquido": round(resultado.valor_final_liquido, 2),
                        "valor_final_liquido_real": round(
                            resultado.valor_final_liquido_real, 2
                        ),
                    },
                    "evolucao_mensal": [
                        {
                            "mes": r["mes"],
                            "total_investido": round(r["total_investido"], 2),
                            "patrimonio_bruto": round(r["patrimonio_bruto"], 2),
                            "rendimento_bruto": round(r["rendimento_bruto"], 2),
                            "aliquota_ir": round(r["aliquota_ir"], 4),
                            "imposto_renda": round(r["imposto_renda"], 2),
                            "patrimonio_liquido": round(r["patrimonio_liquido"], 2),
                            "patrimonio_liquido_real": round(
                                r["patrimonio_liquido_real"], 2
                            ),
                        }
                        for r in registros
                    ],
                }
            )

        if len(identificadores) == 1:
            sufixo = _sanitizar_nome_arquivo(identificadores[0])
            prefixo = "evolucao"
        else:
            sufixo = "_vs_".join(_sanitizar_nome_arquivo(i) for i in identificadores)
            prefixo = "evolucao_comparativa"

        arquivo = self._resolver_caminho_saida(
            prefixo,
            sufixo,
            chave_origem=("json", tuple(identificadores)),
            extensao="json",
        )
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"JSON exportado em: {arquivo}")
        return arquivo

    # ------------------------------------------------------------------
    # GERAR RELATORIO (Markdown consolidado)
    # ------------------------------------------------------------------
    def gerar_relatorio(self, tree):
        nome_entrada = _texto(tree.children[0]).strip()
        if len(tree.children) > 1:
            simbolos = [self.tabela.buscar(_texto(t)) for t in tree.children[1:]]
        else:
            simbolos = self.tabela.listar()

        os.makedirs(self.diretorio_saida, exist_ok=True)
        nome_base = os.path.basename(nome_entrada)
        if not nome_base.lower().endswith(".md"):
            nome_base = f"{_sanitizar_nome_arquivo(nome_base)}.md"
        caminho = os.path.join(self.diretorio_saida, nome_base)

        resultados = [(s, Resultado(s)) for s in simbolos]
        melhor_liquido = max(resultados, key=lambda item: item[1].valor_final_liquido)

        linhas = [
            "# Relatorio Consolidado de Simulacao Financeira",
            "",
            "## 1. Tabela Comparativa de Cenarios",
            "",
            "| Cenario | Prazo (Meses) | Taxa Mensal Efetiva | Total Investido | Rendimento Bruto | Imposto de Renda | Valor Final Liquido | Valor Final Liquido Real |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for s, res in resultados:
            taxa_str = f"{s.taxa * 100:.4f}%"
            linhas.append(
                f"| **{s.identificador}** | {s.periodo} | {taxa_str} | "
                f"{_moeda(res.total_investido)} | {_moeda(res.rendimento_bruto)} | "
                f"{_moeda(res.imposto_renda)} | **{_moeda(res.valor_final_liquido)}** | "
                f"{_moeda(res.valor_final_liquido_real)} |"
            )

        linhas.extend(
            [
                "",
                "## 2. Destaque de Rentabilidade Liquida",
                "",
                f"- Melhor cenario liquido nominal: **{melhor_liquido[0].identificador}** "
                f"com patrimonio liquido final de **{_moeda(melhor_liquido[1].valor_final_liquido)}**.",
            ]
        )

        if self.artefatos_gerados:
            linhas.extend(["", "## 3. Artefatos e Graficos Gerados", ""])
            for art in self.artefatos_gerados:
                nome_art = os.path.basename(art)
                linhas.append(f"- `{nome_art}`")

        linhas.append("")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))

        if caminho not in self.artefatos_gerados:
            self.artefatos_gerados.append(caminho)
        print(f"Relatorio consolidado gerado em: {caminho}")
        return caminho

    # ------------------------------------------------------------------
    # SIMULAR RENDA (Fase de Usufruto / Aposentadoria)
    # ------------------------------------------------------------------
    def simular_renda(self, tree):
        identificador = _texto(tree.children[0])
        valor_retirada = float(tree.children[1])
        unidade = str(tree.children[2])
        retirada_mensal = (
            valor_retirada / 12.0 if unidade == "AO_ANO" else valor_retirada
        )

        simbolo = self.tabela.buscar(identificador)
        resultado = Resultado(simbolo)
        patrimonio_inicial_usufruto = (
            resultado.valor_final_liquido_real
            if simbolo.inflacao > 0
            else resultado.valor_final_liquido
        )

        # Taxa liquida mensal na fase de usufruto (descontando IR sobre rendimentos e taxa de adm)
        aliquota_usufruto = simbolo.aliquota_para_mes(max(1, simbolo.periodo))
        taxa_liquida_nominal = max(
            0.0, simbolo.taxa * (1.0 - aliquota_usufruto) - simbolo.taxa_administracao
        )
        if simbolo.inflacao > 0:
            taxa_mensal_usufruto = max(
                0.0,
                ((1.0 + taxa_liquida_nominal) / (1.0 + simbolo.inflacao)) - 1.0,
            )
        else:
            taxa_mensal_usufruto = taxa_liquida_nominal

        renda_perpetua = patrimonio_inicial_usufruto * taxa_mensal_usufruto

        if taxa_mensal_usufruto > 0 and retirada_mensal <= renda_perpetua + 1e-9:
            perpetua = True
            meses_duracao = math.inf
        elif taxa_mensal_usufruto == 0:
            perpetua = False
            meses_duracao = int(patrimonio_inicial_usufruto // retirada_mensal)
        else:
            perpetua = False
            saldo = patrimonio_inicial_usufruto
            meses_duracao = 0
            # Limite de seguranca de 12000 meses (1000 anos) para evitar laco infinito
            while saldo >= retirada_mensal and meses_duracao < 12000:
                saldo = saldo * (1.0 + taxa_mensal_usufruto) - retirada_mensal
                meses_duracao += 1
            if meses_duracao >= 12000:
                perpetua = True
                meses_duracao = math.inf

        print(f"=== SIMULACAO DE RENDA PASSIVA: {identificador} ===")
        print(f"{'Patrimonio Base:':<21}{_moeda(patrimonio_inicial_usufruto)}")
        print(f"{'Retirada Mensal:':<21}{_moeda(retirada_mensal)}")
        print(f"{'Renda Perpetua Max:':<21}{_moeda(renda_perpetua)}")
        if perpetua:
            print(f"{'Duracao Estimada:':<21}Perpetua (nao consome o principal)")
        else:
            anos = meses_duracao // 12
            meses_rest = meses_duracao % 12
            print(
                f"{'Duracao Estimada:':<21}{meses_duracao} meses "
                f"({anos} anos e {meses_rest} meses)"
            )

        return {
            "identificador": identificador,
            "patrimonio_base": patrimonio_inicial_usufruto,
            "retirada_mensal": retirada_mensal,
            "renda_perpetua_maxima": renda_perpetua,
            "perpetua": perpetua,
            "meses_duracao": meses_duracao,
        }
