"""
Orquestrador de Execucao da AST - AST Visitor (interpretador.py)

Percorre a Arvore Sintatica Abstrata (AST) ja validada via `lark.visitors.Interpreter`
e despacha a execucao de cada comando da linguagem para os componentes
especializados de simulacao financeira (`motor.py`), renderizacao grafica
(`graficos.py`) e exportacao de dados/relatorios (`exportacao.py`).
"""

import os
import re

from lark.visitors import Interpreter

from .exportacao import (
    formatar_moeda as _moeda,
    salvar_csv_evolucao,
    salvar_json_evolucao,
    salvar_relatorio_markdown,
    sanitizar_nome_arquivo as _sanitizar_nome_arquivo,
)
from .graficos import (
    carregar_pyplot as _carregar_pyplot,
    salvar_grafico_comparativo_png,
    salvar_grafico_individual_png,
    salvar_grafico_interativo_html,
)
from .motor import Resultado, calcular_simulacao_renda, simular_serie_detalhada
from .parser import extrair_texto_string as _texto

__all__ = [
    "Interpretador",
    "Resultado",
    "_carregar_pyplot",
    "_moeda",
    "_sanitizar_nome_arquivo",
]


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
    # Fachadas estaticas para o Motor Financeiro
    # ------------------------------------------------------------------
    @staticmethod
    def simular_detalhado(simbolo):
        """Retorna a lista completa de dicionarios mensais (0..n) do investimento."""
        return simular_serie_detalhada(simbolo)

    @staticmethod
    def calcular_simulacao_renda(simbolo, retirada_mensal):
        """Calcula a sustentabilidade de retiradas mensais na fase de usufruto."""
        return calcular_simulacao_renda(simbolo, retirada_mensal)

    # ------------------------------------------------------------------
    # Utilitario de Resolucao de Caminhos de Saida
    # ------------------------------------------------------------------
    def _resolver_caminho_saida(
        self, prefixo, sufixo_base, chave_origem, extensao="png"
    ):
        """Resolve o caminho do arquivo de saida prevenindo colisao entre identificadores distintos."""
        os.makedirs(self.diretorio_saida, exist_ok=True)
        base = f"{prefixo}_{sufixo_base}" if prefixo else sufixo_base
        nome_arquivo = f"{base}.{extensao}"
        contador = 2
        while (
            nome_arquivo in self._arquivos_registrados
            and self._arquivos_registrados[nome_arquivo] != chave_origem
        ):
            nome_arquivo = f"{base}_{contador}.{extensao}"
            contador += 1
        self._arquivos_registrados[nome_arquivo] = chave_origem
        caminho = os.path.join(self.diretorio_saida, nome_arquivo)
        if caminho not in self.artefatos_gerados:
            self.artefatos_gerados.append(caminho)
        return caminho

    # ------------------------------------------------------------------
    # IMPRIMIR RESUMO
    # ------------------------------------------------------------------
    def imprimir_resumo(self, tree):
        """Calcula e exibe no console o resumo consolidado do investimento."""
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
    # GERAR GRAFICO / COMPARAR GRAFICO (Matplotlib PNG)
    # ------------------------------------------------------------------
    def gerar_grafico(self, tree):
        """Gera um grafico PNG individual (ou delega para comparativo se houver varios)."""
        identificadores = [_texto(t) for t in tree.children]
        if len(identificadores) > 1:
            return self.comparar_grafico(tree)

        identificador = identificadores[0]
        simbolo = self.tabela.buscar(identificador)
        registros = simular_serie_detalhada(simbolo)

        nome_seguro = _sanitizar_nome_arquivo(identificador)
        arquivo = self._resolver_caminho_saida(
            "grafico", nome_seguro, chave_origem=("individual", identificador)
        )
        salvar_grafico_individual_png(simbolo, registros, arquivo)
        print(f"Grafico gerado em: {arquivo}")
        return arquivo

    def comparar_grafico(self, tree):
        """Gera um grafico PNG comparando a evolucao de dois ou mais investimentos."""
        identificadores = [_texto(t) for t in tree.children]
        series_por_simbolo = []
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            series_por_simbolo.append((simbolo, simular_serie_detalhada(simbolo)))

        nomes = "_vs_".join(_sanitizar_nome_arquivo(i) for i in identificadores)
        arquivo = self._resolver_caminho_saida(
            "grafico_comparativo",
            nomes,
            chave_origem=("comparativo", tuple(identificadores)),
        )
        salvar_grafico_comparativo_png(series_por_simbolo, arquivo)
        print(f"Grafico comparativo gerado em: {arquivo}")
        return arquivo

    # ------------------------------------------------------------------
    # GERAR GRAFICO_INTERATIVO (HTML Interativo com Plotly)
    # ------------------------------------------------------------------
    def gerar_grafico_interativo(self, tree):
        """Gera um grafico HTML interativo (Plotly) para um ou mais investimentos."""
        identificadores = [_texto(t) for t in tree.children]
        series_por_simbolo = []
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            series_por_simbolo.append((simbolo, simular_serie_detalhada(simbolo)))

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
        salvar_grafico_interativo_html(series_por_simbolo, titulo, arquivo)
        print(f"Grafico interativo gerado em: {arquivo}")
        return arquivo

    # ------------------------------------------------------------------
    # EXPORTAR CSV / EXPORTAR JSON / GERAR RELATORIO
    # ------------------------------------------------------------------
    def exportar_csv(self, tree):
        """Exporta a serie temporal mensal (0..n) de cada investimento informado em CSV."""
        identificadores = [_texto(t) for t in tree.children]
        arquivos = []
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            registros = simular_serie_detalhada(simbolo)
            nome_seguro = _sanitizar_nome_arquivo(identificador)
            arquivo = self._resolver_caminho_saida(
                "evolucao",
                nome_seguro,
                chave_origem=("csv", identificador),
                extensao="csv",
            )
            salvar_csv_evolucao(registros, arquivo)
            print(f"CSV exportado em: {arquivo}")
            arquivos.append(arquivo)
        return arquivos[0] if len(arquivos) == 1 else arquivos

    def exportar_json(self, tree):
        """Exporta parametros, resumo e evolucao mensal dos investimentos em JSON."""
        identificadores = [_texto(t) for t in tree.children]
        itens_simulacao = []
        for identificador in identificadores:
            simbolo = self.tabela.buscar(identificador)
            itens_simulacao.append(
                (simbolo, Resultado(simbolo), simular_serie_detalhada(simbolo))
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
        salvar_json_evolucao(itens_simulacao, arquivo)
        print(f"JSON exportado em: {arquivo}")
        return arquivo

    def gerar_relatorio(self, tree):
        """Gera um relatorio consolidado em Markdown comparando os investimentos."""
        nome_entrada = _texto(tree.children[0]).strip()
        if len(tree.children) > 1:
            simbolos = [self.tabela.buscar(_texto(t)) for t in tree.children[1:]]
        else:
            simbolos = self.tabela.listar()

        nome_limpo = re.sub(r"^(?:\.+[\\/]+)+", "", nome_entrada).strip("/\\.")
        if nome_limpo.lower().endswith(".md"):
            stem = nome_limpo[:-3]
        else:
            stem = nome_limpo
        stem_seguro = _sanitizar_nome_arquivo(stem) if stem.strip() else "relatorio"

        artefatos_anteriores = list(self.artefatos_gerados)
        caminho = self._resolver_caminho_saida(
            None,
            stem_seguro,
            chave_origem=("relatorio", nome_entrada),
            extensao="md",
        )

        resultados = [(s, Resultado(s)) for s in simbolos]
        salvar_relatorio_markdown(resultados, artefatos_anteriores, caminho)
        print(f"Relatorio consolidado gerado em: {caminho}")
        return caminho

    # ------------------------------------------------------------------
    # SIMULAR RENDA (Fase de Usufruto / Aposentadoria)
    # ------------------------------------------------------------------
    def simular_renda(self, tree):
        """Simula e imprime a duracao do patrimonio acumulado sob retiradas periodicas."""
        identificador = _texto(tree.children[0])
        valor_retirada = float(tree.children[1])
        unidade = str(tree.children[2])
        retirada_mensal = (
            valor_retirada / 12.0 if unidade == "AO_ANO" else valor_retirada
        )

        simbolo = self.tabela.buscar(identificador)
        dados = calcular_simulacao_renda(simbolo, retirada_mensal)

        print(f"=== SIMULACAO DE RENDA PASSIVA: {identificador} ===")
        print(f"{'Patrimonio Base:':<21}{_moeda(dados['patrimonio_base'])}")
        print(f"{'Retirada Mensal:':<21}{_moeda(dados['retirada_mensal'])}")
        print(f"{'Renda Perpetua Max:':<21}{_moeda(dados['renda_perpetua_maxima'])}")
        if dados["perpetua"]:
            print(f"{'Duracao Estimada:':<21}Perpetua (nao consome o principal)")
        else:
            meses_duracao = dados["meses_duracao"]
            anos = meses_duracao // 12
            meses_rest = meses_duracao % 12
            print(
                f"{'Duracao Estimada:':<21}{meses_duracao} meses "
                f"({anos} anos e {meses_rest} meses)"
            )

        return dados
