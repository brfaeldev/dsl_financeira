"""
Motor Matematico, Financeiro e Tributario (motor.py)

Concentra todas as equacoes financeiras de juros compostos, valor futuro de
anuidades, simulacao iterativa mes a mes por safras (tranches), consumo FIFO em
resgates parciais, custos de administracao, deflacao pela Equacao de Fisher,
regimes tributarios (fixo, regressivo, por safra e come-cotas), validacao de
viabilidade de saldo para resgates e simulacao da fase de usufruto (renda passiva).
"""

import math

from .erros import ValorForaDoDominioError
from .tabela_simbolos import aliquota_regressiva_ir


def simular_serie_detalhada(simbolo, resgates_com_posicao=None):
    """Executa a simulacao mes a mes (0..n) contemplando todas as regras do dominio.

    Suporta:
    - Aporte inicial (P), aportes mensais recorrentes (PMT) e APORTE_EXTRA por mes;
    - RESGATE parcial por mes (consumindo proporcionalmente capital e rendimento via FIFO);
    - TAXA_ADMINISTRACAO descontada mensalmente sobre o patrimonio;
    - Tributacao fixa, regressiva global, regressiva por safra (tranches) e come-cotas;
    - Deflacao do patrimonio liquido pelo fator acumulado de INFLACAO.

    Se `resgates_com_posicao` (dicionario `{mes: [(valor, linha, coluna), ...]}`)
    for informado, valida a disponibilidade de saldo em cada resgate considerando
    inclusive descontos anteriores de come-cotas, lancando `ValorForaDoDominioError`.
    """
    n = simbolo.periodo
    r = simbolo.taxa
    r_adm = simbolo.taxa_administracao

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
    ir_resgates_acumulado = 0.0
    ir_come_cotas_acumulado = 0.0
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

            # 2.1. Validacao opcional de saldo disponivel para cada evento de resgate no mes
            if resgates_com_posicao and mes in resgates_com_posicao:
                saldo_disponivel = sum(s[2] for s in safras)
                for val_resgate_ev, linha_ev, col_ev in resgates_com_posicao[mes]:
                    if val_resgate_ev > saldo_disponivel + 1e-9:
                        raise ValorForaDoDominioError(
                            simbolo.identificador,
                            "RESGATE",
                            val_resgate_ev,
                            f"O resgate no mes {mes} excede o saldo disponivel ({saldo_disponivel:.2f}).",
                            linha=linha_ev,
                            coluna=col_ev,
                        )
                    saldo_disponivel -= val_resgate_ev

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
                ir_resgates_acumulado += ir_resgate
                total_resgatado_bruto += valor_resgate

            # 4. Regime Come-Cotas semestral (meses 6, 12, 18, ...)
            if simbolo.imposto_come_cotas and mes % 6 == 0:
                for safra in safras:
                    rend_safra = max(0.0, safra[2] - safra[1])
                    if rend_safra > 0:
                        ir_cc = rend_safra * aliquota_come_cotas
                        safra[2] -= ir_cc
                        # Apos a antecipacao semestral, o novo saldo passa a ser a base ja tributada
                        safra[1] = safra[2]
                        ir_come_cotas_acumulado += ir_cc

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
        else:
            aliquota_efetiva = simbolo.aliquota_para_mes(mes)
            ir_latente = rendimento_latente * aliquota_efetiva

        saldo_liquido = saldo_bruto - ir_latente
        fator_inflacao = (1.0 + simbolo.inflacao) ** mes
        saldo_liquido_real = saldo_liquido / fator_inflacao

        # Rendimento bruto total gerado ate o mes:
        # total_resgatado_bruto ja embute a parcela de IR retida nos resgates
        # (ir_resgates_acumulado), enquanto ir_come_cotas_acumulado foi deduzido
        # diretamente do saldo das safras.
        rendimento_bruto_total = (
            saldo_bruto
            + total_resgatado_bruto
            + ir_come_cotas_acumulado
            - total_investido_acumulado
        )
        ir_pago_acumulado = ir_resgates_acumulado + ir_come_cotas_acumulado
        imposto_total_ate_mes = ir_pago_acumulado + ir_latente
        total_resgatado_liquido = total_resgatado_bruto - ir_resgates_acumulado

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


def validar_viabilidade_resgates(simbolo, eventos_pendentes):
    """Valida se os resgates parciais cabem no saldo acumulado do respectivo mes."""
    if not simbolo.resgates:
        return
    resgates_com_posicao = {}
    for tipo_ev, mes_ev, val_ev, linha_ev, col_ev in eventos_pendentes:
        if tipo_ev == "RESGATE":
            resgates_com_posicao.setdefault(mes_ev, []).append(
                (val_ev, linha_ev, col_ev)
            )
    simular_serie_detalhada(simbolo, resgates_com_posicao=resgates_com_posicao)


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
        self.total_resgatado_liquido = 0.0
        self.custo_administracao = 0.0

        if not simbolo.usa_simulacao_detalhada:
            # Formulas fechadas classicas (Secao II-C do artigo IEEE)
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
            ultimo = simular_serie_detalhada(simbolo)[-1]
            self.total_investido = ultimo["total_investido"]
            self.valor_final_bruto = ultimo["patrimonio_bruto"]
            self.rendimento_bruto = ultimo["rendimento_bruto"]
            self.imposto_renda = ultimo["imposto_renda"]
            self.valor_final_liquido = ultimo["patrimonio_liquido"]
            self.total_resgatado = ultimo["total_resgatado_bruto"]
            self.total_resgatado_liquido = ultimo["total_resgatado_liquido"]
            self.custo_administracao = ultimo["custo_administracao"]

        self.patrimonio_liquido_total = (
            self.valor_final_liquido + self.total_resgatado_liquido
        )
        # Deflacao pelo indice de inflacao acumulado no periodo: V_real = V_nominal / (1 + i)^n
        fator_inflacao = (1.0 + simbolo.inflacao) ** n
        self.valor_final_liquido_real = self.valor_final_liquido / fator_inflacao


def calcular_simulacao_renda(simbolo, retirada_mensal):
    """Calcula a sustentabilidade de retiradas mensais na fase de usufruto (aposentadoria)."""
    resultado = Resultado(simbolo)
    patrimonio_inicial_usufruto = (
        resultado.valor_final_liquido_real
        if simbolo.inflacao > 0
        else resultado.valor_final_liquido
    )

    # Taxa liquida mensal na fase de usufruto (descontando taxa de adm e IR sobre rendimentos)
    aliquota_usufruto = simbolo.aliquota_para_mes(max(1, simbolo.periodo))
    taxa_apos_adm = (1.0 + simbolo.taxa) * (1.0 - simbolo.taxa_administracao) - 1.0
    taxa_liquida_nominal = max(0.0, taxa_apos_adm * (1.0 - aliquota_usufruto))
    if simbolo.inflacao > 0:
        taxa_mensal_usufruto = max(
            0.0,
            ((1.0 + taxa_liquida_nominal) / (1.0 + simbolo.inflacao)) - 1.0,
        )
    else:
        taxa_mensal_usufruto = taxa_liquida_nominal

    renda_perpetua = patrimonio_inicial_usufruto * taxa_mensal_usufruto
    curva_usufruto = [patrimonio_inicial_usufruto]

    if taxa_mensal_usufruto > 0 and retirada_mensal <= renda_perpetua + 1e-9:
        perpetua = True
        meses_duracao = math.inf
    elif taxa_mensal_usufruto == 0:
        perpetua = False
        meses_duracao = int(patrimonio_inicial_usufruto // retirada_mensal)
        saldo = patrimonio_inicial_usufruto
        for _ in range(min(meses_duracao, 1200)):
            saldo = max(0.0, saldo - retirada_mensal)
            curva_usufruto.append(saldo)
    else:
        perpetua = False
        saldo = patrimonio_inicial_usufruto
        meses_duracao = 0
        # Limite de seguranca de 12000 meses (1000 anos) para evitar laco infinito;
        # em cada mes o saldo rende juros antes da retirada de fim de mes.
        while (
            saldo * (1.0 + taxa_mensal_usufruto) >= retirada_mensal - 1e-9
            and meses_duracao < 12000
        ):
            saldo = max(0.0, saldo * (1.0 + taxa_mensal_usufruto) - retirada_mensal)
            meses_duracao += 1
            if meses_duracao <= 1200:
                curva_usufruto.append(saldo)
        if meses_duracao >= 12000:
            perpetua = True
            meses_duracao = math.inf

    return {
        "identificador": simbolo.identificador,
        "patrimonio_base": patrimonio_inicial_usufruto,
        "retirada_mensal": retirada_mensal,
        "renda_perpetua_maxima": renda_perpetua,
        "perpetua": perpetua,
        "meses_duracao": meses_duracao,
        "curva_usufruto": curva_usufruto,
    }
