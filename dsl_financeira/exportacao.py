"""
Formatacao, Exportacao de Dados e Relatorios (exportacao.py)

Centraliza a formatacao monetaria no padrao brasileiro, a sanitizacao de nomes
de arquivos e a geracao de artefatos em CSV, JSON e Relatorios Markdown.
"""

import csv
import json
import os
import re

CAMPOS_CSV_PADRAO = [
    "mes",
    "total_investido",
    "patrimonio_bruto",
    "rendimento_bruto",
    "aliquota_ir",
    "imposto_renda",
    "patrimonio_liquido",
    "patrimonio_liquido_real",
    "total_resgatado_bruto",
    "custo_administracao",
]


def formatar_moeda(valor):
    """Formata um numero no padrao monetario brasileiro (R$ 1.234,56)."""
    texto = f"{valor:,.2f}"
    # Converte separador de milhar (',' -> '.') e decimal ('.' -> ',') usando '#' como pivo
    texto = texto.replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {texto}"


def sanitizar_nome_arquivo(identificador):
    """Substitui espacos e caracteres invalidos de sistema de arquivos por underscore."""
    limpo = re.sub(r'[\\/:*?"<>|\s]+', "_", identificador.strip())
    return limpo.strip("_") or "investimento"


def escrever_csv_registros(registros, stream, campos=None):
    """Escreve uma lista de dicionarios mensais em um stream no formato CSV."""
    colunas = campos if campos is not None else CAMPOS_CSV_PADRAO
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(colunas)
    for reg in registros:
        writer.writerow(
            [
                reg[c]
                if c == "mes"
                else (f"{reg[c]:.4f}" if c == "aliquota_ir" else f"{reg[c]:.2f}")
                for c in colunas
            ]
        )


def salvar_csv_evolucao(registros, caminho_arquivo):
    """Salva a evolucao mensal de um investimento em arquivo CSV."""
    with open(caminho_arquivo, "w", newline="", encoding="utf-8") as f:
        escrever_csv_registros(registros, f, campos=CAMPOS_CSV_PADRAO)
    return caminho_arquivo


def salvar_json_evolucao(itens_simulacao, caminho_arquivo):
    """Salva os parametros, resumo e serie temporal de um ou mais investimentos em JSON."""
    payload = {"investimentos": []}
    for simbolo, resultado, registros in itens_simulacao:
        payload["investimentos"].append(
            {
                "identificador": simbolo.identificador,
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
                    "total_resgatado_bruto": round(resultado.total_resgatado, 2),
                    "total_resgatado_liquido": round(
                        resultado.total_resgatado_liquido, 2
                    ),
                    "custo_administracao": round(resultado.custo_administracao, 2),
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
                        "total_resgatado_bruto": round(
                            r["total_resgatado_bruto"], 2
                        ),
                        "custo_administracao": round(r["custo_administracao"], 2),
                    }
                    for r in registros
                ],
            }
        )
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return caminho_arquivo


def salvar_relatorio_markdown(resultados_por_simbolo, artefatos_gerados, caminho_arquivo):
    """Gera e salva o relatorio executivo consolidado em formato Markdown."""
    melhor_liquido = max(
        resultados_por_simbolo,
        key=lambda item: item[1].patrimonio_liquido_total,
    )

    linhas = [
        "# Relatorio Consolidado de Simulacao Financeira",
        "",
        "## 1. Tabela Comparativa de Cenarios",
        "",
        "| Cenario | Prazo (Meses) | Taxa Mensal Efetiva | Total Investido | Rendimento Bruto | Imposto de Renda | Valor Final Liquido | Valor Final Liquido Real |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for s, res in resultados_por_simbolo:
        taxa_str = f"{s.taxa * 100:.4f}%"
        linhas.append(
            f"| **{s.identificador}** | {s.periodo} | {taxa_str} | "
            f"{formatar_moeda(res.total_investido)} | {formatar_moeda(res.rendimento_bruto)} | "
            f"{formatar_moeda(res.imposto_renda)} | **{formatar_moeda(res.valor_final_liquido)}** | "
            f"{formatar_moeda(res.valor_final_liquido_real)} |"
        )

    linhas.extend(
        [
            "",
            "## 2. Destaque de Rentabilidade Liquida",
            "",
            f"- Melhor cenario liquido nominal: **{melhor_liquido[0].identificador}** "
            f"com patrimonio liquido final de **{formatar_moeda(melhor_liquido[1].valor_final_liquido)}**.",
        ]
    )

    if artefatos_gerados:
        linhas.extend(["", "## 3. Artefatos e Graficos Gerados", ""])
        for art in artefatos_gerados:
            nome_art = os.path.basename(art)
            linhas.append(f"- `{nome_art}`")

    linhas.append("")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    return caminho_arquivo
