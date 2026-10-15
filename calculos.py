"""
Motor de cálculo (mesma lógica do PREC-EXTRA-2018-2020.py).
Este módulo NÃO lê arquivos nem usa Streamlit: recebe DataFrames prontos
e devolve o DataFrame do relatório. Assim pode ser testado isoladamente.
"""
import pandas as pd

LIMITE_FASE1 = pd.Timestamp("2021-12-01")
LIMITE_FASE2 = pd.Timestamp("2025-08-01")
JUROS_MENSAL_FASE3 = 0.001666666666


# ==============================================================================
# 1. BUSCA DE ÍNDICES
# ==============================================================================
def obter_n_indice(df_idx, data_alvo):
    data_alvo_padrao = data_alvo.replace(day=1)
    mascara = df_idx["data"] == data_alvo_padrao
    if not mascara.any():
        df_filtrado = df_idx[df_idx["data"] <= data_alvo_padrao]
        if df_filtrado.empty:
            return 0.0
        return df_filtrado.iloc[-1]["n_indice"]
    return df_idx.loc[mascara, "n_indice"].values[0]


# ==============================================================================
# 2. VARIAÇÕES
# ==============================================================================
def obter_variacao_ipca15(df_ipca15, d_ini, d_fim):
    if d_ini >= d_fim:
        return 0.0
    idx_ini = obter_n_indice(df_ipca15, d_ini)
    idx_fim = obter_n_indice(df_ipca15, d_fim)
    if idx_ini == 0:
        return 0.0
    return (idx_fim / idx_ini) - 1.0


def obter_variacao_poupanca(df_poup, d_ini, d_fim):
    if d_ini >= d_fim:
        return 0.0
    return (obter_n_indice(df_poup, d_fim) - obter_n_indice(df_poup, d_ini)) / 100.0


def obter_variacao_selic(df_selic, d_ini, d_fim):
    if d_ini >= d_fim:
        return 0.0
    return obter_n_indice(df_selic, d_fim) - obter_n_indice(df_selic, d_ini)


def obter_variacao_ipca(df_ipca, d_ini, d_fim):
    if d_ini >= d_fim:
        return 0.0
    idx_ini = obter_n_indice(df_ipca, d_ini)
    idx_fim = obter_n_indice(df_ipca, d_fim)
    if idx_ini == 0:
        return 0.0
    return (idx_fim / idx_ini) - 1.0


def calcular_meses_inteiros(data_inicio, data_fim):
    if data_inicio >= data_fim:
        return 0
    return (data_fim.year - data_inicio.year) * 12 + (data_fim.month - data_inicio.month)


# ==============================================================================
# 3. ATUALIZAÇÃO SEM PAGAMENTO (MARCOS DE TRANSIÇÃO)
# ==============================================================================
def atualizar_valores_fase(p, j, d_ini, d_fim, limite_graca, bases):
    df_ipca15, df_poup, df_selic, df_ipca = bases
    t = d_ini
    while t < d_fim:
        if t < limite_graca:
            next_t = min(d_fim, limite_graca)
            var_ipca = obter_variacao_ipca15(df_ipca15, t, next_t)
            p = p * (1 + var_ipca)
            j = j * (1 + var_ipca)
        elif t < LIMITE_FASE1:
            next_t = min(d_fim, LIMITE_FASE1)
            var_ipca = obter_variacao_ipca15(df_ipca15, t, next_t)
            var_poup = obter_variacao_poupanca(df_poup, t, next_t)
            p_new = p * (1 + var_ipca)
            j = j * (1 + var_ipca) + (p_new * var_poup)
            p = p_new
        elif t < LIMITE_FASE2:
            next_t = min(d_fim, LIMITE_FASE2)
            var_selic = obter_variacao_selic(df_selic, t, next_t)
            j = j + ((p + j) * var_selic)
        else:
            next_t = d_fim
            var_ipca = obter_variacao_ipca(df_ipca, t, next_t)
            var_juros = calcular_meses_inteiros(t, next_t) * JUROS_MENSAL_FASE3
            p_new = p * (1 + var_ipca)
            j = j * (1 + var_ipca) + (p_new * var_juros)
            p = p_new
        t = next_t
    return p, j


def _taxas_exibidas(data_ref, last_date, limite_graca, bases):
    """Regra ativa e taxas mostradas no relatório para uma data de referência."""
    df_ipca15, df_poup, df_selic, df_ipca = bases
    if data_ref <= limite_graca:
        return ("IPCA-15 (Graça)", obter_variacao_ipca15(df_ipca15, last_date, data_ref), 0.0)
    if data_ref <= LIMITE_FASE1:
        m = max(last_date, limite_graca)
        return ("IPCA-15 + POUP", obter_variacao_ipca15(df_ipca15, m, data_ref),
                obter_variacao_poupanca(df_poup, m, data_ref))
    if data_ref <= LIMITE_FASE2:
        m = max(last_date, LIMITE_FASE1)
        return ("SELIC SIMPLES", obter_variacao_selic(df_selic, m, data_ref), 0.0)
    m = max(last_date, LIMITE_FASE2)
    return ("IPCA + JUROS", obter_variacao_ipca(df_ipca, m, data_ref),
            calcular_meses_inteiros(m, data_ref) * JUROS_MENSAL_FASE3)


# ==============================================================================
# 4. ESTEIRA UNIFICADA COM AMORTIZAÇÃO PROPORCIONAL
# ==============================================================================
def processar_esteira_completa(pagamentos, principal_inicial, juros_inicial,
                               data_inicial, limite_graca, data_atual, bases):
    """
    pagamentos: DataFrame com colunas 'ordem_pagamento', 'data_pagamento' (datetime)
                e 'Valor_Depositado' (float). Somente pagamentos (ordem > 0).
    """
    pagamentos = pagamentos.copy()
    pagamentos["data_pagamento"] = pd.to_datetime(pagamentos["data_pagamento"]).apply(
        lambda dt: dt.replace(day=1))
    pagamentos = pagamentos.sort_values("data_pagamento", kind="stable")

    historico = []
    current_p, current_j, last_date = principal_inicial, juros_inicial, data_inicial

    for _, row in pagamentos.iterrows():
        current_date = row["data_pagamento"]
        deposito = float(row["Valor_Depositado"])

        val_p, val_j = atualizar_valores_fase(current_p, current_j, last_date,
                                              current_date, limite_graca, bases)
        total = val_p + val_j
        fase, taxa_idx, taxa_jur = _taxas_exibidas(current_date, last_date, limite_graca, bases)

        perc_p = val_p / total if total > 0 else 0.0
        perc_j = val_j / total if total > 0 else 0.0
        abat_p, abat_j = perc_p * deposito, perc_j * deposito
        saldo_p, saldo_j = max(0.0, val_p - abat_p), max(0.0, val_j - abat_j)

        historico.append({
            "ordem_pagamento": int(row["ordem_pagamento"]),
            "data_pagamento": current_date.strftime("%m/%Y"),
            "Regra_Ativa": fase,
            "IPCA_Selic_Aplicado": taxa_idx,
            "Juros_Aplicado": taxa_jur,
            "valor_principal_proposta": val_p,
            "juros_proposta": val_j,
            "Total_data_pagto": total,
            "Valor_Depositado": deposito,
            "Per_Prin_Pagto": abat_p,
            "Per_Juros_Pagto": abat_j,
            "Saldo_Principal": saldo_p,
            "Saldo_Juros": saldo_j,
            "Saldo_Total": saldo_p + saldo_j,
        })
        current_p, current_j, last_date = saldo_p, saldo_j, current_date

    if last_date < data_atual:
        val_p, val_j = atualizar_valores_fase(current_p, current_j, last_date,
                                              data_atual, limite_graca, bases)
        _, taxa_idx, taxa_jur = _taxas_exibidas(data_atual, last_date, limite_graca, bases)
        historico.append({
            "ordem_pagamento": "FINAL",
            "data_pagamento": data_atual.strftime("%m/%Y"),
            "Regra_Ativa": "ENCERRAMENTO",
            "IPCA_Selic_Aplicado": taxa_idx,
            "Juros_Aplicado": taxa_jur,
            "valor_principal_proposta": val_p,
            "juros_proposta": val_j,
            "Total_data_pagto": val_p + val_j,
            "Valor_Depositado": 0.0,
            "Per_Prin_Pagto": 0.0,
            "Per_Juros_Pagto": 0.0,
            "Saldo_Principal": val_p,
            "Saldo_Juros": val_j,
            "Saldo_Total": val_p + val_j,
        })

    return pd.DataFrame(historico, columns=COLUNAS_RELATORIO)


COLUNAS_RELATORIO = [
    "ordem_pagamento", "data_pagamento", "Regra_Ativa", "IPCA_Selic_Aplicado", "Juros_Aplicado",
    "valor_principal_proposta", "juros_proposta", "Total_data_pagto",
    "Valor_Depositado", "Per_Prin_Pagto", "Per_Juros_Pagto",
    "Saldo_Principal", "Saldo_Juros", "Saldo_Total",
]
