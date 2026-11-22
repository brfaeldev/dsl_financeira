"""
Playground Web e Mini-IDE da DSL Financeira em Streamlit (app.py)

Como executar:
    streamlit run app.py

Oferece:
1. Editor interativo de codigo .dsl com carregamento dos exemplos do projeto;
2. Assistente Visual na barra lateral que gera blocos INDICE e INVESTIMENTO na sintaxe da DSL;
3. Dashboard Financeiro com cards de metricas, tabela comparativa, graficos e downloads (CSV/JSON/MD);
4. Simulador interativo de Renda Passiva (fase de usufruto/aposentadoria);
5. Raio-X do Compilador: inspecao dos Tokens Lexicos, Arvore Sintatica Abstrata (AST) e Tabela de Simbolos.
"""

import contextlib
import io
import json
import math
import os
import tempfile

from lark.exceptions import LarkError

from dsl_financeira import (
    AnalisadorSemantico,
    Interpretador,
    Resultado,
    analisar,
    criar_parser,
)
from dsl_financeira.erros import ErroSemantico
from dsl_financeira.interpretador import _carregar_pyplot, _moeda

_DIRETORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
_DIRETORIO_EXEMPLOS = os.path.join(_DIRETORIO_RAIZ, "exemplos")


# ----------------------------------------------------------------------
# Funcoes puras do Playground (testaveis sem iniciar servidor Streamlit)
# ----------------------------------------------------------------------
def listar_exemplos_disponiveis():
    """Retorna um dicionario {nome_arquivo: caminho_absoluto} dos scripts .dsl em exemplos/."""
    if not os.path.isdir(_DIRETORIO_EXEMPLOS):
        return {}
    arquivos = sorted(
        f for f in os.listdir(_DIRETORIO_EXEMPLOS) if f.lower().endswith(".dsl")
    )
    return {nome: os.path.join(_DIRETORIO_EXEMPLOS, nome) for nome in arquivos}


def gerar_declaracao_indice_dsl(nome, taxa, unidade="AO_ANO"):
    """Gera uma linha valida de declaracao de INDICE na sintaxe da DSL."""
    nome_limpo = nome.strip().replace('"', "") or "CDI"
    return f'INDICE "{nome_limpo}" {float(taxa):.2f} PORCENTO {unidade}'


def gerar_bloco_investimento_dsl(
    nome,
    valor_inicial=0.0,
    usar_aporte=True,
    aporte_mensal=500.0,
    prazo=12,
    unidade_prazo="MESES",
    modo_taxa="Prefixada",
    taxa_valor=1.0,
    unidade_taxa="AO_MES",
    indice_taxa="CDI",
    modo_inflacao="Nenhuma",
    inflacao_valor=4.5,
    unidade_inflacao="AO_ANO",
    indice_inflacao="IPCA",
    taxa_administracao=0.0,
    modo_imposto="REGRESSIVO",
    aliquota_fixa=15.0,
):
    """Monta um bloco INVESTIMENTO ... FIM e seu comando IMPRIMIR RESUMO na sintaxe da DSL."""
    nome_limpo = nome.strip().replace('"', "") or "Meu_Investimento"
    linhas = [f'INVESTIMENTO "{nome_limpo}"']

    if valor_inicial > 0 or not usar_aporte:
        linhas.append(f"    VALOR_INICIAL {float(valor_inicial):.2f}")

    if usar_aporte and aporte_mensal > 0:
        linhas.append(
            f"    APORTE {float(aporte_mensal):.2f} POR {int(prazo)} {unidade_prazo}"
        )
    else:
        linhas.append(f"    PERIODO {int(prazo)} {unidade_prazo}")

    if modo_taxa == "Pos-Fixada (% de Indice)":
        linhas.append(
            f'    TAXA {float(taxa_valor):.2f} PORCENTO DO "{indice_taxa.strip()}"'
        )
    elif modo_taxa == "Hibrida (Indice + Taxa Fixa)":
        linhas.append(
            f'    TAXA "{indice_taxa.strip()}" + {float(taxa_valor):.2f} PORCENTO {unidade_taxa}'
        )
    else:
        linhas.append(
            f"    TAXA {float(taxa_valor):.2f} PORCENTO {unidade_taxa}"
        )

    if taxa_administracao > 0:
        linhas.append(
            f"    TAXA_ADMINISTRACAO {float(taxa_administracao):.2f} PORCENTO AO_ANO"
        )

    if modo_inflacao == "Taxa Explicita":
        linhas.append(
            f"    INFLACAO {float(inflacao_valor):.2f} PORCENTO {unidade_inflacao}"
        )
    elif modo_inflacao == "Usar Indice":
        linhas.append(f'    INFLACAO "{indice_inflacao.strip()}"')

    if modo_imposto == "REGRESSIVO":
        linhas.append("    IMPOSTO REGRESSIVO")
    elif modo_imposto == "REGRESSIVO POR_SAFRA":
        linhas.append("    IMPOSTO REGRESSIVO POR_SAFRA")
    elif modo_imposto == "COME_COTAS":
        linhas.append("    IMPOSTO COME_COTAS")
    elif modo_imposto == "Fixo / Isento":
        linhas.append(f"    IMPOSTO {float(aliquota_fixa):.2f} PORCENTO")

    linhas.append("FIM")
    linhas.append(f'IMPRIMIR RESUMO "{nome_limpo}"')
    return "\n".join(linhas)


def compilar_e_simular_dsl(codigo):
    """Executa o pipeline completo da DSL em memoria para o Playground Web.

    Retorna um dicionario com:
        - sucesso (bool)
        - tipo_erro (None | 'Semantico' | 'Sintaxe' | 'Execucao')
        - mensagem_erro (str | None)
        - linha_erro (int | None)
        - coluna_erro (int | None)
        - tokens (list[dict])
        - ast_pretty (str)
        - tabela (TabelaSimbolos | None)
        - resultados (list[tuple[Investimento, Resultado, list[dict]]])
        - console_output (str)
    """
    resposta = {
        "sucesso": False,
        "tipo_erro": None,
        "mensagem_erro": None,
        "linha_erro": None,
        "coluna_erro": None,
        "tokens": [],
        "ast_pretty": "",
        "tabela": None,
        "resultados": [],
        "console_output": "",
    }

    try:
        parser = criar_parser("lalr")
        tokens_raw = list(parser.lex(codigo))
        resposta["tokens"] = [
            {
                "Tipo (Token)": t.type,
                "Lexema (Valor)": str(t),
                "Linha": t.line,
                "Coluna": t.column,
            }
            for t in tokens_raw
        ]

        ast = analisar(codigo, parser="lalr")
        resposta["ast_pretty"] = ast.pretty()

        analisador = AnalisadorSemantico()
        tabela = analisador.analisar(ast)
        resposta["tabela"] = tabela

        buffer_console = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            interpretador = Interpretador(tabela, diretorio_saida=tmpdir)
            with contextlib.redirect_stdout(buffer_console):
                interpretador.executar(ast)

        resposta["console_output"] = buffer_console.getvalue()

        resultados = []
        for simbolo in tabela.listar():
            res = Resultado(simbolo)
            serie = Interpretador.simular_detalhado(simbolo)
            resultados.append((simbolo, res, serie))

        resposta["resultados"] = resultados
        resposta["sucesso"] = True
    except ErroSemantico as erro:
        resposta["tipo_erro"] = "Semantico"
        resposta["mensagem_erro"] = str(erro)
        resposta["linha_erro"] = getattr(erro, "linha", None)
        resposta["coluna_erro"] = getattr(erro, "coluna", None)
    except LarkError as erro:
        resposta["tipo_erro"] = "Sintaxe"
        resposta["mensagem_erro"] = str(erro)
        resposta["linha_erro"] = getattr(erro, "line", None)
        resposta["coluna_erro"] = getattr(erro, "column", None)
    except Exception as erro:
        resposta["tipo_erro"] = "Execucao"
        resposta["mensagem_erro"] = str(erro)

    return resposta


# ----------------------------------------------------------------------
# Interface Grafica Streamlit
# ----------------------------------------------------------------------
def renderizar_app():
    import streamlit as st

    st.set_page_config(
        page_title="DSL Financeira — Playground & Compilador",
        page_icon="📈",
        layout="wide",
    )

    exemplos = listar_exemplos_disponiveis()
    padrao_inicial = ""
    if "comparacao_cenarios.dsl" in exemplos:
        with open(exemplos["comparacao_cenarios.dsl"], "r", encoding="utf-8") as f:
            padrao_inicial = f.read()

    if "codigo_dsl" not in st.session_state:
        st.session_state["codigo_dsl"] = padrao_inicial

    # ------------------------------------------------------------------
    # Barra Lateral: Exemplos e Construtor Visual de Codigo DSL
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("⚙️ Ferramentas da DSL")

        st.subheader("1. Scripts de Exemplo")
        if exemplos:
            nome_exemplo = st.selectbox(
                "Escolha um exemplo da pasta exemplos/:",
                options=list(exemplos.keys()),
                index=(
                    list(exemplos.keys()).index("comparacao_cenarios.dsl")
                    if "comparacao_cenarios.dsl" in exemplos
                    else 0
                ),
            )
            if st.button("📂 Carregar Exemplo no Editor", use_container_width=True):
                with open(exemplos[nome_exemplo], "r", encoding="utf-8") as f:
                    st.session_state["codigo_dsl"] = f.read()
                st.rerun()

        st.divider()
        st.subheader("2. Assistente Visual (Gerador DSL)")

        with st.expander("➕ Adicionar Indexador (INDICE)", expanded=False):
            ind_nome = st.text_input("Nome do Índice", value="CDI", key="ind_nome")
            ind_taxa = st.number_input(
                "Taxa (%)", min_value=0.0, value=10.75, step=0.25, key="ind_taxa"
            )
            ind_unid = st.selectbox(
                "Unidade", options=["AO_ANO", "AO_MES"], key="ind_unid"
            )
            if st.button("Inserir INDICE no Topo", use_container_width=True):
                linha_ind = gerar_declaracao_indice_dsl(ind_nome, ind_taxa, ind_unid)
                st.session_state["codigo_dsl"] = (
                    linha_ind + "\n" + st.session_state["codigo_dsl"]
                )
                st.rerun()

        with st.expander("➕ Adicionar Bloco INVESTIMENTO", expanded=False):
            inv_nome = st.text_input(
                "Nome do Investimento", value="Novo_Cenario", key="inv_nome"
            )
            inv_p = st.number_input(
                "Valor Inicial (R$)",
                min_value=0.0,
                value=5000.0,
                step=500.0,
                key="inv_p",
            )
            inv_tem_aporte = st.checkbox(
                "Possui aporte mensal recorrente?", value=True, key="inv_tem_aporte"
            )
            inv_pmt = (
                st.number_input(
                    "Aporte Mensal (R$)",
                    min_value=0.0,
                    value=500.0,
                    step=100.0,
                    key="inv_pmt",
                )
                if inv_tem_aporte
                else 0.0
            )
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                inv_prazo = st.number_input(
                    "Prazo", min_value=1, value=12, step=1, key="inv_prazo"
                )
            with col_p2:
                inv_unid_p = st.selectbox(
                    "Unidade Prazo", options=["MESES", "ANOS"], key="inv_unid_p"
                )

            inv_modo_taxa = st.selectbox(
                "Tipo de Taxa",
                options=[
                    "Prefixada",
                    "Pos-Fixada (% de Indice)",
                    "Hibrida (Indice + Taxa Fixa)",
                ],
                key="inv_modo_taxa",
            )
            inv_taxa_val = st.number_input(
                "Valor / Percentual da Taxa (%)",
                min_value=0.0,
                value=1.0,
                step=0.1,
                key="inv_taxa_val",
            )
            inv_unid_t = st.selectbox(
                "Unidade da Taxa", options=["AO_MES", "AO_ANO"], key="inv_unid_t"
            )
            inv_ind_t = (
                st.text_input("Nome do Índice da Taxa", value="CDI", key="inv_ind_t")
                if inv_modo_taxa != "Prefixada"
                else "CDI"
            )

            inv_modo_inf = st.selectbox(
                "Correção por Inflação",
                options=["Nenhuma", "Taxa Explicita", "Usar Indice"],
                key="inv_modo_inf",
            )
            inv_inf_val = (
                st.number_input(
                    "Inflação (%)",
                    min_value=0.0,
                    value=4.5,
                    step=0.25,
                    key="inv_inf_val",
                )
                if inv_modo_inf == "Taxa Explicita"
                else 4.5
            )
            inv_unid_inf = (
                st.selectbox(
                    "Unidade Inflação",
                    options=["AO_ANO", "AO_MES"],
                    key="inv_unid_inf",
                )
                if inv_modo_inf == "Taxa Explicita"
                else "AO_ANO"
            )
            inv_ind_inf = (
                st.text_input(
                    "Nome do Índice de Inflação", value="IPCA", key="inv_ind_inf"
                )
                if inv_modo_inf == "Usar Indice"
                else "IPCA"
            )

            inv_adm = st.number_input(
                "Taxa de Administração (% a.a.)",
                min_value=0.0,
                max_value=99.0,
                value=0.0,
                step=0.1,
                key="inv_adm",
            )

            inv_imp = st.selectbox(
                "Regime de Imposto de Renda",
                options=[
                    "REGRESSIVO",
                    "REGRESSIVO POR_SAFRA",
                    "COME_COTAS",
                    "Fixo / Isento",
                ],
                key="inv_imp",
            )
            inv_aliq = (
                st.number_input(
                    "Alíquota Fixa (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=15.0,
                    step=2.5,
                    key="inv_aliq",
                )
                if inv_imp == "Fixo / Isento"
                else 15.0
            )

            if st.button("Inserir INVESTIMENTO no Código", use_container_width=True):
                bloco = gerar_bloco_investimento_dsl(
                    nome=inv_nome,
                    valor_inicial=inv_p,
                    usar_aporte=inv_tem_aporte,
                    aporte_mensal=inv_pmt,
                    prazo=inv_prazo,
                    unidade_prazo=inv_unid_p,
                    modo_taxa=inv_modo_taxa,
                    taxa_valor=inv_taxa_val,
                    unidade_taxa=inv_unid_t,
                    indice_taxa=inv_ind_t,
                    modo_inflacao=inv_modo_inf,
                    inflacao_valor=inv_inf_val,
                    unidade_inflacao=inv_unid_inf,
                    indice_inflacao=inv_ind_inf,
                    taxa_administracao=inv_adm,
                    modo_imposto=inv_imp,
                    aliquota_fixa=inv_aliq,
                )
                st.session_state["codigo_dsl"] = (
                    st.session_state["codigo_dsl"].rstrip() + "\n\n" + bloco + "\n"
                )
                st.rerun()

    # ------------------------------------------------------------------
    # Cabecalho Principal e Editor da DSL
    # ------------------------------------------------------------------
    st.title("📈 DSL Financeira — Playground & Inspetor do Compilador")
    st.caption(
        "Linguagem de Domínio Específico declarativa para modelagem e simulação financeira de investimentos "
        "(Front-End Lark LALR(1) + AST Visitor + Tabela de Símbolos)."
    )

    with st.expander("📝 Editor de Código (.dsl)", expanded=True):
        codigo_atual = st.text_area(
            "Escreva ou edite seu script .dsl abaixo:",
            value=st.session_state["codigo_dsl"],
            height=260,
        )
        st.session_state["codigo_dsl"] = codigo_atual

        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.button(
                "▶️ Compilar e Executar Script DSL",
                type="primary",
                use_container_width=True,
            )
        with col_btn2:
            st.download_button(
                "💾 Baixar Script (.dsl)",
                data=codigo_atual.encode("utf-8"),
                file_name="cenario_simulacao.dsl",
                mime="text/plain",
                use_container_width=True,
            )

    if not codigo_atual.strip():
        st.info("Digite ou carregue um script `.dsl` na barra lateral para iniciar.")
        return

    resultado_exec = compilar_e_simular_dsl(codigo_atual)

    # ------------------------------------------------------------------
    # Exibicao de Erros Lexicos, Sintaticos ou Semanticos
    # ------------------------------------------------------------------
    if not resultado_exec["sucesso"]:
        tipo = resultado_exec["tipo_erro"]
        msg = resultado_exec["mensagem_erro"]
        st.error(f"**[Erro {tipo}]** {msg}")

        linha_err = resultado_exec["linha_erro"]
        if linha_err is not None:
            linhas_cod = codigo_atual.splitlines()
            if 1 <= linha_err <= len(linhas_cod):
                st.code(
                    f"Linha {linha_err}: {linhas_cod[linha_err - 1]}",
                    language="text",
                )
        return

    resultados = resultado_exec["resultados"]
    tabela = resultado_exec["tabela"]

    # ------------------------------------------------------------------
    # Abas de Resultados e Inspecao do Compilador
    # ------------------------------------------------------------------
    aba_dash, aba_renda, aba_compilador, aba_console = st.tabs(
        [
            "📊 1. Dashboard & Gráficos",
            "🏖️ 2. Simulador de Renda Passiva (Usufruto)",
            "🔍 3. Raio-X do Compilador (AST & Tabela de Símbolos)",
            "💻 4. Saída do Console & Gramática EBNF",
        ]
    )

    # ==================================================================
    # ABA 1: Dashboard Financeiro & Graficos
    # ==================================================================
    with aba_dash:
        if not resultados:
            st.warning(
                "O script foi compilado com sucesso, mas não há blocos INVESTIMENTO declarados."
            )
        else:
            melhor_sim, melhor_res, _ = max(
                resultados, key=lambda item: item[1].valor_final_liquido
            )
            st.success(
                f"🏆 **Melhor Cenário Líquido**: `{melhor_sim.identificador}` com patrimônio líquido final de "
                f"**{_moeda(melhor_res.valor_final_liquido)}** "
                f"(Poder de Compra Real: **{_moeda(melhor_res.valor_final_liquido_real)}**)."
            )

            # Cards de resumo para cada investimento
            for simbolo, res, _ in resultados:
                st.markdown(f"#### 📌 Cenário: `{simbolo.identificador}`")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Total Investido", _moeda(res.total_investido))
                c2.metric("Rendimento Bruto", _moeda(res.rendimento_bruto))
                c3.metric(
                    "Imposto de Renda",
                    _moeda(res.imposto_renda),
                    delta=f"-{simbolo.imposto * 100:.1f}% base",
                    delta_color="inverse",
                )
                c4.metric("Valor Final Líquido", _moeda(res.valor_final_liquido))
                c5.metric(
                    "Valor Líquido Real",
                    _moeda(res.valor_final_liquido_real),
                    help="Patrimônio líquido deflacionado pelo índice de inflação acumulado.",
                )

            st.divider()
            st.subheader("📋 Tabela Comparativa Consolidada")
            tabela_comparativa = []
            for simbolo, res, _ in resultados:
                tabela_comparativa.append(
                    {
                        "Cenário": simbolo.identificador,
                        "Prazo (Meses)": simbolo.periodo,
                        "Taxa Mensal Efetiva": f"{simbolo.taxa * 100:.4f}%",
                        "Inflação Mensal": f"{simbolo.inflacao * 100:.4f}%",
                        "Total Investido": _moeda(res.total_investido),
                        "Rendimento Bruto": _moeda(res.rendimento_bruto),
                        "Imposto de Renda": _moeda(res.imposto_renda),
                        "Total Resgatado": _moeda(res.total_resgatado),
                        "Valor Final Líquido": _moeda(res.valor_final_liquido),
                        "Valor Líquido Real": _moeda(res.valor_final_liquido_real),
                    }
                )
            st.dataframe(tabela_comparativa, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("📈 Curvas de Crescimento Patrimonial")
            plt = _carregar_pyplot()
            fig, ax = plt.subplots(figsize=(10, 5))
            for simbolo, _, serie in resultados:
                meses = [r["mes"] for r in serie]
                liq = [r["patrimonio_liquido"] for r in serie]
                bruto = [r["patrimonio_bruto"] for r in serie]
                linha = ax.plot(
                    meses,
                    liq,
                    linewidth=2.2,
                    label=f"{simbolo.identificador} (Líquido)",
                )
                cor = linha[0].get_color()
                ax.plot(
                    meses,
                    bruto,
                    linestyle="--",
                    alpha=0.55,
                    color=cor,
                    label=f"{simbolo.identificador} (Bruto)",
                )
                if simbolo.inflacao > 0:
                    real = [r["patrimonio_liquido_real"] for r in serie]
                    ax.plot(
                        meses,
                        real,
                        linestyle=":",
                        alpha=0.9,
                        color=cor,
                        label=f"{simbolo.identificador} (Líquido Real)",
                    )
            ax.set_title("Evolução Patrimonial Mês a Mês")
            ax.set_xlabel("Meses")
            ax.set_ylabel("Valor (R$)")
            ax.grid(True, alpha=0.35)
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            # Inspecao da tabela mensal + Exportacao CSV/JSON
            st.subheader("📑 Série Temporal Mês a Mês e Exportação")
            nomes_inv = [s.identificador for s, _, _ in resultados]
            inv_selecionado = st.selectbox(
                "Selecione um investimento para inspecionar a evolução mensal (0..n):",
                options=nomes_inv,
            )
            _, res_sel, serie_sel = next(
                item for item in resultados if item[0].identificador == inv_selecionado
            )
            st.dataframe(serie_sel, use_container_width=True, hide_index=True)

            # Prepara CSV e JSON para download direto
            buf_csv = io.StringIO()
            campos_csv = list(serie_sel[0].keys())
            buf_csv.write(",".join(campos_csv) + "\n")
            for linha_s in serie_sel:
                buf_csv.write(
                    ",".join(
                        str(linha_s[c]) if c == "mes" else f"{linha_s[c]:.2f}"
                        for c in campos_csv
                    )
                    + "\n"
                )

            payload_json = {
                "cenario": inv_selecionado,
                "resumo": {
                    "total_investido": round(res_sel.total_investido, 2),
                    "rendimento_bruto": round(res_sel.rendimento_bruto, 2),
                    "imposto_renda": round(res_sel.imposto_renda, 2),
                    "valor_final_liquido": round(res_sel.valor_final_liquido, 2),
                    "valor_final_liquido_real": round(
                        res_sel.valor_final_liquido_real, 2
                    ),
                },
                "evolucao_mensal": serie_sel,
            }

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    f"⬇️ Baixar Evolução Mensal de '{inv_selecionado}' (.csv)",
                    data=buf_csv.getvalue().encode("utf-8"),
                    file_name=f"evolucao_{inv_selecionado}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_dl2:
                st.download_button(
                    f"⬇️ Baixar Dados Completos de '{inv_selecionado}' (.json)",
                    data=json.dumps(payload_json, indent=2, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                    file_name=f"evolucao_{inv_selecionado}.json",
                    mime="application/json",
                    use_container_width=True,
                )

    # ==================================================================
    # ABA 2: Simulador Interativo de Renda Passiva (Usufruto)
    # ==================================================================
    with aba_renda:
        if not resultados:
            st.info("Declare ao menos um investimento para simular a fase de usufruto.")
        else:
            st.markdown(
                "Simule por quantos meses e anos o patrimônio líquido acumulado sustenta "
                "uma retirada mensal na aposentadoria (equivalente ao comando `SIMULAR RENDA`)."
            )
            nomes_inv = [s.identificador for s, _, _ in resultados]
            cenario_renda = st.selectbox(
                "Investimento base para aposentadoria:",
                options=nomes_inv,
                key="sel_renda",
            )
            sim_r, res_r, _ = next(
                item for item in resultados if item[0].identificador == cenario_renda
            )

            patrimonio_base = (
                res_r.valor_final_liquido_real
                if sim_r.inflacao > 0
                else res_r.valor_final_liquido
            )
            aliquota_u = sim_r.aliquota_para_mes(max(1, sim_r.periodo))
            taxa_liq_nom = max(
                0.0, sim_r.taxa * (1.0 - aliquota_u) - sim_r.taxa_administracao
            )
            taxa_usufruto = (
                max(0.0, ((1.0 + taxa_liq_nom) / (1.0 + sim_r.inflacao)) - 1.0)
                if sim_r.inflacao > 0
                else taxa_liq_nom
            )
            renda_perpetua = patrimonio_base * taxa_usufruto

            retirada_escolhida = st.number_input(
                "Retirada Mensal Desejada (R$):",
                min_value=10.0,
                value=float(max(100.0, round(renda_perpetua * 1.5, 2))),
                step=100.0,
            )

            cr1, cr2, cr3 = st.columns(3)
            cr1.metric("Patrimônio Base Acumulado", _moeda(patrimonio_base))
            cr2.metric(
                "Renda Perpétua Máxima",
                _moeda(renda_perpetua),
                help="Valor máximo que você pode retirar todo mês sem nunca consumir o patrimônio principal.",
            )

            if taxa_usufruto > 0 and retirada_escolhida <= renda_perpetua + 1e-9:
                cr3.metric("Duração Estimada", "Perpétua ( Vitalícia )")
                st.success(
                    f"Com retirada de **{_moeda(retirada_escolhida)}/mês** (abaixo ou igual à renda perpétua de "
                    f"**{_moeda(renda_perpetua)}/mês**), o patrimônio **nunca se esgota**!"
                )
            else:
                saldo_u = patrimonio_base
                meses_u = 0
                curva_usufruto = [saldo_u]
                while saldo_u >= retirada_escolhida and meses_u < 1200:
                    saldo_u = saldo_u * (1.0 + taxa_usufruto) - retirada_escolhida
                    meses_u += 1
                    curva_usufruto.append(max(0.0, saldo_u))
                anos_u = meses_u // 12
                resto_m = meses_u % 12
                cr3.metric(
                    "Duração Estimada",
                    f"{meses_u} meses ({anos_u}a {resto_m}m)",
                )
                st.line_chart(curva_usufruto)

    # ==================================================================
    # ABA 3: Raio-X do Compilador (Tokens, AST e Tabela de Simbolos)
    # ==================================================================
    with aba_compilador:
        st.markdown(
            "Esta visão expõe as estruturas internas construídas pelas três fases do interpretador: "
            "**1. Análise Léxica (Tokens)** → **2. Análise Sintática (AST Lark)** → **3. Análise Semântica (Tabela de Símbolos)**."
        )

        st.subheader("1. Tabela de Símbolos (`TabelaSimbolos`)")
        indices_decl = tabela.listar_indices()
        if indices_decl:
            st.markdown("**Indexadores Macroeconômicos Globais (`_indices`):**")
            st.dataframe(
                [
                    {
                        "Identificador": k,
                        "Taxa Mensal Equivalente (decimal)": f"{v:.8f}",
                        "Taxa Mensal (%)": f"{v * 100:.4f}%",
                        "Taxa Anual Equivalente (%)": f"{((1 + v) ** 12 - 1) * 100:.2f}%",
                    }
                    for k, v in indices_decl.items()
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**Entidades de Investimento (`_simbolos`):**")
        linhas_simbolos = []
        for s in tabela.listar():
            linhas_simbolos.append(
                {
                    "identificador": s.identificador,
                    "valor_inicial (P)": s.valor_inicial,
                    "aporte (PMT)": s.aporte,
                    "periodo (n meses)": s.periodo,
                    "taxa mensal (r)": round(s.taxa, 8),
                    "inflacao mensal (i)": round(s.inflacao, 8),
                    "taxa_adm mensal": round(s.taxa_administracao, 8),
                    "imposto base (t)": s.imposto,
                    "regressivo": s.imposto_regressivo,
                    "por_safra": s.imposto_por_safra,
                    "come_cotas": s.imposto_come_cotas,
                    "aportes_extras": str(s.aportes_extras),
                    "resgates": str(s.resgates),
                }
            )
        st.dataframe(linhas_simbolos, use_container_width=True, hide_index=True)

        col_ast, col_tok = st.columns(2)
        with col_ast:
            st.subheader("2. Árvore Sintática Abstrata (AST)")
            st.code(resultado_exec["ast_pretty"], language="text")
        with col_tok:
            st.subheader(
                f"3. Fluxo de Tokens Léxicos ({len(resultado_exec['tokens'])} tokens)"
            )
            st.dataframe(
                resultado_exec["tokens"],
                use_container_width=True,
                hide_index=True,
                height=380,
            )

    # ==================================================================
    # ABA 4: Saida Textual do Console & Gramatica EBNF
    # ==================================================================
    with aba_console:
        st.subheader("Saída Padrão do Interpretador (`stdout`)")
        st.code(
            resultado_exec["console_output"]
            or "(Nenhuma saída de terminal gerada pelos comandos do script)",
            language="text",
        )
        st.subheader("Gramática Formal EBNF (`dsl_financeira/gramatica.lark`)")
        caminho_gram = os.path.join(_DIRETORIO_RAIZ, "dsl_financeira", "gramatica.lark")
        if os.path.exists(caminho_gram):
            with open(caminho_gram, "r", encoding="utf-8") as fg:
                st.code(fg.read(), language="text")


if __name__ == "__main__":
    renderizar_app()
