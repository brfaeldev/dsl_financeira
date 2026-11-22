"""
Analisador Semantico - AST Visitor (semantico.py)

Percorre a Arvore Sintatica Abstrata (AST) via `lark.visitors.Interpreter` para
popular a Tabela de Simbolos (indexadores e investimentos), garantindo a
unicidade de declaracoes, a presenca de parametros obrigatorios, a conversao de
unidades temporais (AO_ANO/ANOS para base mensal), a validade de dominios
numericos e o escopo de uso nos comandos.
"""

from lark.visitors import Interpreter

from .erros import (
    InvestimentoNaoDeclaradoError,
    ParametroDuplicadoError,
    ParametroObrigatorioError,
    ValorForaDoDominioError,
)
from .tabela_simbolos import TabelaSimbolos, aliquota_regressiva_ir


def _texto(token):
    """Remove as aspas externas de um token literal STRING (ex.: '"CDB"' -> 'CDB')."""
    return str(token)[1:-1]


def _posicao(no):
    """Extrai (linha, coluna) de um no Tree (via meta) ou Token folha do Lark."""
    if hasattr(no, "meta") and not getattr(no.meta, "empty", True):
        return getattr(no.meta, "line", None), getattr(no.meta, "column", None)
    return getattr(no, "line", None), getattr(no, "column", None)


def _converter_periodo_para_meses(prazo, unidade_token):
    """Converte um prazo em MESES ou ANOS para o total equivalente em meses."""
    if str(unidade_token) == "ANOS":
        return prazo * 12
    return prazo


def _converter_taxa_para_mensal(percentual, unidade_token):
    """Converte uma taxa percentual (AO_MES ou AO_ANO) para taxa decimal mensal equivalente.

    Para taxas anuais, aplica a equivalencia de juros compostos:
        r_mensal = (1 + r_anual)^(1/12) - 1
    """
    taxa_decimal = percentual / 100.0
    if str(unidade_token) == "AO_ANO":
        return (1.0 + taxa_decimal) ** (1.0 / 12.0) - 1.0
    return taxa_decimal


class AnalisadorSemantico(Interpreter):
    """AST Visitor (Lark Interpreter) responsavel por alimentar a Tabela de Simbolos.

    Diferente de lark.Visitor (bottom-up), a classe Interpreter percorre a AST
    top-down, permitindo controlar o contexto do bloco INVESTIMENTO atual antes
    de visitar seus parametros filhos.
    """

    def __init__(self, tabela=None):
        super().__init__()
        self.tabela = tabela if tabela is not None else TabelaSimbolos()
        # Contexto temporario do bloco INVESTIMENTO sendo validado no momento
        self._simbolo_atual = None
        self._vistos_atual = set()
        self._eventos_pendentes = []

    def analisar(self, ast):
        """Percorre a AST validando declaracoes, parametros e comandos."""
        self.visit(ast)
        return self.tabela

    # ------------------------------------------------------------------
    # Declaracao de Indexadores Macroeconomicos (CDI, SELIC, IPCA, etc.)
    # ------------------------------------------------------------------
    def declaracao_indice(self, tree):
        identificador = _texto(tree.children[0])
        linha, coluna = _posicao(tree)
        if not identificador.strip():
            raise ValorForaDoDominioError(
                identificador,
                "INDICE",
                f'"{identificador}"',
                "O identificador do indice nao pode ser vazio.",
                linha=linha,
                coluna=coluna,
            )
        valor = float(tree.children[1])
        unidade = tree.children[2]
        if valor < 0:
            raise ValorForaDoDominioError(
                identificador,
                "INDICE",
                valor,
                "A taxa do indice nao pode ser negativa.",
                linha=linha,
                coluna=coluna,
            )
        taxa_mensal = _converter_taxa_para_mensal(valor, unidade)
        self.tabela.declarar_indice(
            identificador, taxa_mensal, linha=linha, coluna=coluna
        )

    # ------------------------------------------------------------------
    # Declaracoes de Investimento e bloco de parametros
    # ------------------------------------------------------------------
    def declaracao(self, tree):
        identificador = _texto(tree.children[0])
        linha, coluna = _posicao(tree)
        if not identificador.strip():
            raise ValorForaDoDominioError(
                identificador,
                "INVESTIMENTO",
                f'"{identificador}"',
                "O identificador do investimento nao pode ser vazio.",
                linha=linha,
                coluna=coluna,
            )

        simbolo = self.tabela.declarar(identificador, linha=linha, coluna=coluna)

        self._simbolo_atual = simbolo
        self._vistos_atual = set()
        self._eventos_pendentes = []
        try:
            # Visita o no bloco_parametros, disparando os metodos de cada parametro
            self.visit(tree.children[1])

            # Todo investimento precisa ter um horizonte temporal (> 0 meses),
            # definido via PERIODO <n> (MESES|ANOS) ou via APORTE <v> POR <n> (MESES|ANOS).
            if "periodo_definido" not in self._vistos_atual or simbolo.periodo <= 0:
                raise ParametroObrigatorioError(
                    identificador,
                    "PERIODO <n> MESES/ANOS ou APORTE <valor> POR <n> MESES/ANOS",
                    linha=linha,
                    coluna=coluna,
                )

            # Todo investimento precisa declarar capital (VALOR_INICIAL e/ou APORTE)
            # com montante positivo.
            if (
                "valor_inicial" not in self._vistos_atual
                and "aporte" not in self._vistos_atual
            ):
                raise ParametroObrigatorioError(
                    identificador,
                    "VALOR_INICIAL <valor> ou APORTE <valor> POR <n> MESES/ANOS",
                    linha=linha,
                    coluna=coluna,
                )
            if simbolo.valor_inicial <= 0 and simbolo.aporte <= 0:
                raise ValorForaDoDominioError(
                    identificador,
                    "VALOR_INICIAL / APORTE",
                    0.0,
                    "O investimento deve possuir capital positivo (valor inicial ou aporte maior que zero).",
                    linha=linha,
                    coluna=coluna,
                )

            # Valida se todos os eventos de fluxo de caixa (APORTE_EXTRA / RESGATE)
            # ocorrem dentro do horizonte temporal [1, periodo].
            for tipo_evento, mes_ev, _, linha_ev, col_ev in self._eventos_pendentes:
                if mes_ev <= 0 or mes_ev > simbolo.periodo:
                    raise ValorForaDoDominioError(
                        identificador,
                        f"{tipo_evento} NO_MES",
                        mes_ev,
                        f"O mes do evento deve estar entre 1 e {simbolo.periodo}.",
                        linha=linha_ev,
                        coluna=col_ev,
                    )

            # A aliquota regressiva ou de come-cotas depende do prazo final (n),
            # por isso e resolvida ao encerrar a leitura de todos os parametros do bloco.
            if simbolo.imposto_come_cotas:
                simbolo.imposto = 0.20 if simbolo.periodo <= 12 else 0.15
            elif simbolo.imposto_regressivo:
                simbolo.imposto = aliquota_regressiva_ir(simbolo.periodo)

            # Verifica se algum resgate parcial excede o saldo disponivel no mes
            self._validar_viabilidade_resgates(simbolo)
        except Exception:
            # Rollback: evita manter simbolo invalido/incompleto na Tabela de Simbolos
            self.tabela.remover(identificador)
            raise
        finally:
            # Garante limpeza do estado de bloco mesmo se uma excecao for lancada
            self._simbolo_atual = None
            self._vistos_atual = set()
            self._eventos_pendentes = []

    def _validar_viabilidade_resgates(self, simbolo):
        """Verifica se os resgates parciais nao ultrapassam o saldo acumulado no respectivo mes."""
        if not simbolo.resgates:
            return
        extras_por_mes = {}
        for mes_e, val_e in simbolo.aportes_extras:
            extras_por_mes[mes_e] = extras_por_mes.get(mes_e, 0.0) + val_e

        resgates_info = {}
        for tipo_ev, mes_ev, val_ev, linha_ev, col_ev in self._eventos_pendentes:
            if tipo_ev == "RESGATE":
                resgates_info.setdefault(mes_ev, []).append((val_ev, linha_ev, col_ev))

        saldo = simbolo.valor_inicial
        fator_mensal = (1.0 + simbolo.taxa) * (1.0 - simbolo.taxa_administracao)
        for mes in range(1, simbolo.periodo + 1):
            saldo = saldo * fator_mensal + simbolo.aporte + extras_por_mes.get(mes, 0.0)
            for val_resgate, linha_ev, col_ev in resgates_info.get(mes, []):
                if val_resgate > saldo + 1e-9:
                    raise ValorForaDoDominioError(
                        simbolo.identificador,
                        "RESGATE",
                        val_resgate,
                        f"O resgate no mes {mes} excede o saldo disponivel ({saldo:.2f}).",
                        linha=linha_ev,
                        coluna=col_ev,
                    )
                saldo -= val_resgate

    def _registrar_parametro(
        self, nome, tree, grupo=None, rotulo_conflito=None, mensagem_conflito=None
    ):
        """Registra a ocorrencia de um parametro no bloco atual e impede duplicatas.

        O argumento `grupo` permite bloquear parametros mutuamente exclusivos
        (ex.: declarar APORTE ... POR <n> MESES e PERIODO <n> MESES juntos, ou
        multiplas modalidades de IMPOSTO ou TAXA no mesmo investimento).
        """
        identificador = self._simbolo_atual.identificador
        linha, coluna = _posicao(tree)
        if nome in self._vistos_atual:
            raise ParametroDuplicadoError(
                identificador, nome.upper(), linha=linha, coluna=coluna
            )
        if grupo and grupo in self._vistos_atual:
            raise ParametroDuplicadoError(
                identificador,
                rotulo_conflito or grupo.upper(),
                mensagem=mensagem_conflito,
                linha=linha,
                coluna=coluna,
            )
        self._vistos_atual.add(nome)
        if grupo:
            self._vistos_atual.add(grupo)

    def valor_inicial(self, tree):
        self._registrar_parametro("valor_inicial", tree)
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "VALOR_INICIAL",
                valor,
                "O valor inicial nao pode ser negativo.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.valor_inicial = valor

    def aporte(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "aporte",
            tree,
            grupo="periodo_definido",
            rotulo_conflito="PERIODO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"'APORTE ... POR <n> MESES/ANOS' e 'PERIODO <n> MESES/ANOS'."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        prazo = int(tree.children[1])
        unidade = tree.children[2]
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE",
                valor,
                "O aporte mensal nao pode ser negativo.",
                linha=linha,
                coluna=coluna,
            )
        if prazo <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                f"APORTE ... {unidade}",
                prazo,
                "O periodo deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.aporte = valor
        simbolo.periodo = _converter_periodo_para_meses(prazo, unidade)

    def aporte_extra(self, tree):
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        mes = int(tree.children[1])
        if valor <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "APORTE_EXTRA",
                valor,
                "O valor do aporte extra deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.aportes_extras.append((mes, valor))
        self._eventos_pendentes.append(("APORTE_EXTRA", mes, valor, linha, coluna))

    def resgate(self, tree):
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        mes = int(tree.children[1])
        if valor <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "RESGATE",
                valor,
                "O valor do resgate deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.resgates.append((mes, valor))
        self._eventos_pendentes.append(("RESGATE", mes, valor, linha, coluna))

    def periodo(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "periodo",
            tree,
            grupo="periodo_definido",
            rotulo_conflito="PERIODO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"'APORTE ... POR <n> MESES/ANOS' e 'PERIODO <n> MESES/ANOS'."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        prazo = int(tree.children[0])
        unidade = tree.children[1]
        if prazo <= 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                f"PERIODO ... {unidade}",
                prazo,
                "O periodo deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.periodo = _converter_periodo_para_meses(prazo, unidade)

    def taxa(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "taxa",
            tree,
            grupo="taxa_definida",
            rotulo_conflito="TAXA",
            mensagem_conflito=(
                f"Investimento '{identificador}': parametro 'TAXA' declarado mais de uma vez."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        unidade = tree.children[1]
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA",
                valor,
                "A taxa de juros nao pode ser negativa.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.taxa = _converter_taxa_para_mensal(valor, unidade)

    def taxa_indexada(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "taxa_indexada",
            tree,
            grupo="taxa_definida",
            rotulo_conflito="TAXA",
            mensagem_conflito=(
                f"Investimento '{identificador}': parametro 'TAXA' declarado mais de uma vez."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        percentual = float(tree.children[0])
        token_indice = tree.children[1]
        nome_indice = _texto(token_indice)
        if percentual < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA",
                percentual,
                "O percentual do indexador nao pode ser negativo.",
                linha=linha,
                coluna=coluna,
            )
        linha_ind, col_ind = _posicao(token_indice)
        taxa_indice = self.tabela.buscar_indice(
            nome_indice, linha=linha_ind, coluna=col_ind
        )
        simbolo.taxa = (percentual / 100.0) * taxa_indice

    def _aplicar_taxa_hibrida(self, tree, token_indice, token_valor, token_unidade):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "taxa_hibrida",
            tree,
            grupo="taxa_definida",
            rotulo_conflito="TAXA",
            mensagem_conflito=(
                f"Investimento '{identificador}': parametro 'TAXA' declarado mais de uma vez."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(token_valor)
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA",
                valor,
                "A taxa prefixada adicional nao pode ser negativa.",
                linha=linha,
                coluna=coluna,
            )
        nome_indice = _texto(token_indice)
        linha_ind, col_ind = _posicao(token_indice)
        taxa_indice = self.tabela.buscar_indice(
            nome_indice, linha=linha_ind, coluna=col_ind
        )
        taxa_fixa = _converter_taxa_para_mensal(valor, token_unidade)
        # Composicao de taxas: (1 + r_indice) * (1 + r_fixa) - 1
        simbolo.taxa = (1.0 + taxa_indice) * (1.0 + taxa_fixa) - 1.0

    def taxa_hibrida_indice_primeiro(self, tree):
        self._aplicar_taxa_hibrida(
            tree, tree.children[0], tree.children[1], tree.children[2]
        )

    def taxa_hibrida_fixa_primeiro(self, tree):
        self._aplicar_taxa_hibrida(
            tree, tree.children[2], tree.children[0], tree.children[1]
        )

    def taxa_administracao(self, tree):
        self._registrar_parametro("taxa_administracao", tree)
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        unidade = tree.children[1]
        if valor < 0 or valor >= 100:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "TAXA_ADMINISTRACAO",
                valor,
                "A taxa de administracao deve estar entre 0 e 100 porcento.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.taxa_administracao = _converter_taxa_para_mensal(valor, unidade)

    def inflacao(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "inflacao",
            tree,
            grupo="inflacao_definida",
            rotulo_conflito="INFLACAO",
            mensagem_conflito=(
                f"Investimento '{identificador}': parametro 'INFLACAO' declarado mais de uma vez."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        unidade = tree.children[1]
        if valor < 0:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "INFLACAO",
                valor,
                "A taxa de inflacao nao pode ser negativa.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.inflacao = _converter_taxa_para_mensal(valor, unidade)

    def inflacao_indice(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "inflacao_indice",
            tree,
            grupo="inflacao_definida",
            rotulo_conflito="INFLACAO",
            mensagem_conflito=(
                f"Investimento '{identificador}': parametro 'INFLACAO' declarado mais de uma vez."
            ),
        )
        simbolo = self._simbolo_atual
        token_indice = tree.children[0]
        nome_indice = _texto(token_indice)
        linha_ind, col_ind = _posicao(token_indice)
        simbolo.inflacao = self.tabela.buscar_indice(
            nome_indice, linha=linha_ind, coluna=col_ind
        )

    def imposto(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "imposto",
            tree,
            grupo="imposto_definido",
            rotulo_conflito="IMPOSTO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"'IMPOSTO <valor> PORCENTO' e 'IMPOSTO REGRESSIVO'."
            ),
        )
        simbolo = self._simbolo_atual
        linha, coluna = _posicao(tree)
        valor = float(tree.children[0])
        if valor < 0 or valor > 100:
            raise ValorForaDoDominioError(
                simbolo.identificador,
                "IMPOSTO",
                valor,
                "A aliquota deve estar entre 0 e 100 porcento.",
                linha=linha,
                coluna=coluna,
            )
        simbolo.imposto = valor / 100.0

    def imposto_regressivo(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "imposto_regressivo",
            tree,
            grupo="imposto_definido",
            rotulo_conflito="IMPOSTO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"'IMPOSTO <valor> PORCENTO' e 'IMPOSTO REGRESSIVO'."
            ),
        )
        self._simbolo_atual.imposto_regressivo = True

    def imposto_regressivo_safra(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "imposto_regressivo_safra",
            tree,
            grupo="imposto_definido",
            rotulo_conflito="IMPOSTO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"modalidades de 'IMPOSTO'."
            ),
        )
        self._simbolo_atual.imposto_regressivo = True
        self._simbolo_atual.imposto_por_safra = True

    def imposto_come_cotas(self, tree):
        identificador = self._simbolo_atual.identificador
        self._registrar_parametro(
            "imposto_come_cotas",
            tree,
            grupo="imposto_definido",
            rotulo_conflito="IMPOSTO",
            mensagem_conflito=(
                f"Investimento '{identificador}': conflito de parametros entre "
                f"modalidades de 'IMPOSTO'."
            ),
        )
        self._simbolo_atual.imposto_come_cotas = True

    # ------------------------------------------------------------------
    # Comandos (validacao de escopo declare-before-use e argumentos)
    # ------------------------------------------------------------------
    def _validar_identificadores_comando(self, tree, nome_comando, tokens=None):
        """Verifica se os investimentos referenciados existem e nao se repetem no comando."""
        vistos = set()
        lista_tokens = tokens if tokens is not None else tree.children
        for token in lista_tokens:
            identificador = _texto(token)
            linha, coluna = _posicao(token)
            self.tabela.buscar(identificador, linha=linha, coluna=coluna)
            if identificador in vistos:
                raise ParametroDuplicadoError(
                    identificador,
                    nome_comando,
                    mensagem=(
                        f"Comando '{nome_comando}': o investimento "
                        f"'{identificador}' foi informado mais de uma vez."
                    ),
                    linha=linha,
                    coluna=coluna,
                )
            vistos.add(identificador)

    def imprimir_resumo(self, tree):
        token = tree.children[0]
        linha, coluna = _posicao(token)
        self.tabela.buscar(_texto(token), linha=linha, coluna=coluna)

    def gerar_grafico(self, tree):
        self._validar_identificadores_comando(tree, "GERAR GRAFICO")

    def gerar_grafico_interativo(self, tree):
        self._validar_identificadores_comando(tree, "GERAR GRAFICO_INTERATIVO")

    def comparar_grafico(self, tree):
        self._validar_identificadores_comando(tree, "COMPARAR GRAFICO")

    def exportar_csv(self, tree):
        self._validar_identificadores_comando(tree, "EXPORTAR CSV")

    def exportar_json(self, tree):
        self._validar_identificadores_comando(tree, "EXPORTAR JSON")

    def gerar_relatorio(self, tree):
        linha, coluna = _posicao(tree)
        nome_arquivo = _texto(tree.children[0])
        if not nome_arquivo.strip():
            raise ValorForaDoDominioError(
                "<relatorio>",
                "GERAR RELATORIO",
                f'"{nome_arquivo}"',
                "O nome do arquivo de relatorio nao pode ser vazio.",
                linha=linha,
                coluna=coluna,
            )
        if len(tree.children) > 1:
            self._validar_identificadores_comando(
                tree, "GERAR RELATORIO", tokens=tree.children[1:]
            )
        elif not self.tabela.listar():
            raise InvestimentoNaoDeclaradoError(
                "<nenhum investimento declarado>",
                linha=linha,
                coluna=coluna,
                mensagem="Comando 'GERAR RELATORIO': nenhum investimento foi declarado.",
            )

    def simular_renda(self, tree):
        token_id = tree.children[0]
        identificador = _texto(token_id)
        linha_id, col_id = _posicao(token_id)
        self.tabela.buscar(identificador, linha=linha_id, coluna=col_id)

        retirada = float(tree.children[1])
        linha, coluna = _posicao(tree)
        if retirada <= 0:
            raise ValorForaDoDominioError(
                identificador,
                "SIMULAR RENDA ... RETIRADA",
                retirada,
                "O valor da retirada periodica deve ser maior que zero.",
                linha=linha,
                coluna=coluna,
            )
