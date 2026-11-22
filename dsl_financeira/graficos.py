"""
Renderizacao Grafica Estatica e Interativa (graficos.py)

Encapsula a geracao de graficos de evolucao patrimonial em PNG via Matplotlib
(individuais e comparativos) e de graficos interativos autocontidos em HTML
via Plotly.js.
"""

import json
import sys


def carregar_pyplot():
    """Importa matplotlib.pyplot garantindo o backend headless 'Agg'."""
    if "matplotlib.pyplot" not in sys.modules:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def finalizar_e_salvar_figura(plt, fig, ax, titulo, caminho_arquivo):
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


def salvar_grafico_individual_png(simbolo, registros, caminho_arquivo):
    """Plota e salva o grafico PNG individual de um investimento (bruto, liquido, real e investido)."""
    meses = [r["mes"] for r in registros]
    patrimonio_bruto = [r["patrimonio_bruto"] for r in registros]
    patrimonio_liquido = [r["patrimonio_liquido"] for r in registros]
    investido = [r["total_investido"] for r in registros]

    plt = carregar_pyplot()
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

    finalizar_e_salvar_figura(
        plt,
        fig,
        ax,
        f"Curva de crescimento do patrimonio: {simbolo.identificador}",
        caminho_arquivo,
    )
    return caminho_arquivo


def salvar_grafico_comparativo_png(series_por_simbolo, caminho_arquivo):
    """Plota e salva o grafico PNG comparando multiplos investimentos lado a lado."""
    plt = carregar_pyplot()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for simbolo, registros in series_por_simbolo:
        identificador = simbolo.identificador
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

    finalizar_e_salvar_figura(
        plt,
        fig,
        ax,
        "Analise comparativa de crescimento do patrimonio entre cenarios",
        caminho_arquivo,
    )
    return caminho_arquivo


def salvar_grafico_interativo_html(series_por_simbolo, titulo, caminho_arquivo):
    """Gera e salva um arquivo HTML interativo autocontido utilizando Plotly.js."""
    traces = []
    unico = len(series_por_simbolo) == 1
    for simbolo, registros in series_por_simbolo:
        identificador = simbolo.identificador
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
                    "y": [round(r["patrimonio_liquido_real"], 2) for r in registros],
                    "mode": "lines",
                    "line": {"dash": "dot"},
                    "name": f"{identificador} (Liquido Real)",
                }
            )
        if unico:
            traces.append(
                {
                    "x": meses,
                    "y": [round(r["total_investido"], 2) for r in registros],
                    "mode": "lines",
                    "line": {"dash": "dashdot"},
                    "name": "Total Investido",
                }
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
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(conteudo_html)
    return caminho_arquivo
