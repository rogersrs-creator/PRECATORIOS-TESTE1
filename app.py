"""
App Streamlit - Atualização de Precatórios (Propostas 2012-2020)
Executar localmente:  streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

import config
from calculos import processar_esteira_completa
from fontes import carregar_todas, para_numero
from relatorio import gerar_csv, gerar_excel, tabela_para_tela

st.set_page_config(page_title="Atualização de Precatórios", page_icon="📊", layout="wide")


# ------------------------------------------------------------------------------
# Bases de índices (cache de 1 hora; botão na barra lateral força recarga)
# ------------------------------------------------------------------------------
def obter_urls() -> dict:
    urls = dict(config.PLANILHAS)
    try:
        if "planilhas" in st.secrets:
            urls.update({k.upper(): v for k, v in st.secrets["planilhas"].items()})
    except Exception:
        pass  # sem secrets.toml: usa config.py
    return urls


@st.cache_data(ttl=3600, show_spinner="Carregando índices...")
def carregar_bases_cache(urls_itens: tuple):
    return carregar_todas(dict(urls_itens))


with st.sidebar:
    st.header("Bases de índices")
    if st.button("🔄 Recarregar índices", use_container_width=True):
        carregar_bases_cache.clear()
        st.session_state.pop("resultado", None)

try:
    bases, df_graca, origens = carregar_bases_cache(tuple(sorted(obter_urls().items())))
except Exception as e:
    st.error(f"Não foi possível carregar as bases de índices.\n\n**Detalhe:** {e}")
    st.stop()

nomes_bases = ["IPCA-15", "Poupança", "SELIC", "IPCA"]
with st.sidebar:
    for nome, df in zip(nomes_bases, bases):
        st.caption(f"**{nome}**: {len(df)} meses · até {df['data'].max():%m/%Y}")
    with st.expander("Origem dos dados"):
        for k, v in origens.items():
            st.write(f"{k}: {v}")

ultima_data_comum = min(df["data"].max() for df in bases)

# ------------------------------------------------------------------------------
# Formulário de entrada
# ------------------------------------------------------------------------------
ANO_MIN, ANO_MAX = 2018, 2020   # este app usa somente o motor das propostas 2018 a 2020

st.title(f"📊 Atualização de Precatórios – Propostas {ANO_MIN} a {ANO_MAX}")

anos = sorted(a for a in df_graca["ANO_PROPOSTA"].tolist() if ANO_MIN <= a <= ANO_MAX)
if not anos:
    st.error(f"A planilha GRACA não tem nenhuma proposta entre {ANO_MIN} e {ANO_MAX}.")
    st.stop()

PAGAMENTOS_VAZIOS = pd.DataFrame({
    "Data de Pagamento": pd.Series(dtype="datetime64[ns]"),
    "Valor Depositado": pd.Series(dtype="float"),
})

with st.form("form_calculo"):
    st.subheader("Dados da proposta")
    c1, c2, c3, c4 = st.columns(4)
    ano_proposta = c1.selectbox("Ano da proposta", anos, index=None,
                                placeholder="Selecione o ano...")
    data_final = c2.date_input("Data final da dívida", value=date.today().replace(day=1),
                               format="DD/MM/YYYY",
                               help="Só o mês/ano é considerado (o dia é ajustado para 1º).")
    principal_txt = c3.text_input("Valor principal (R$)", placeholder="Ex.: 871,04")
    juros_txt = c4.text_input("Juros (R$)", value="0,00")

    st.subheader("Pagamentos efetuados")
    st.caption("Adicione uma linha por pagamento (botão **+** abaixo da tabela). "
               "A ordem é numerada automaticamente pela data. Deixe vazia se não houve pagamento.")
    pagamentos_editados = st.data_editor(
        PAGAMENTOS_VAZIOS,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_pagamentos",
        column_config={
            "Data de Pagamento": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
            "Valor Depositado": st.column_config.NumberColumn(
                format="R$ %.2f", min_value=0.0, step=0.01, required=True),
        },
    )

    enviado = st.form_submit_button("Calcular", type="primary", use_container_width=True)

# ------------------------------------------------------------------------------
# Validação e cálculo
# ------------------------------------------------------------------------------
if enviado:
    erros = []
    if ano_proposta is None:
        st.error("Selecione o **ano da proposta** antes de calcular.")
        st.session_state.pop("resultado", None)
        st.stop()
    principal = para_numero(principal_txt)
    juros = para_numero(juros_txt) if juros_txt.strip() else 0.0
    if pd.isna(principal) or principal <= 0:
        erros.append("Informe um **valor principal** válido (ex.: 871,04).")
    if pd.isna(juros) or juros < 0:
        erros.append("Informe um valor de **juros** válido (use 0,00 se não houver).")

    pags = pagamentos_editados.dropna(how="all").copy()
    if pags[["Data de Pagamento", "Valor Depositado"]].isna().any().any():
        erros.append("Há pagamentos com **data ou valor em branco**. Preencha ou remova a linha.")

    linha_graca = df_graca[df_graca["ANO_PROPOSTA"] == ano_proposta].iloc[0]
    data_inicial = linha_graca["DATA_BASE_INICIAL_CALCULOS"]
    fim_graca = linha_graca["FIM_PER_GRACA"]
    data_final_ts = pd.Timestamp(data_final).replace(day=1)

    if not erros:
        pags["data_pagamento"] = pd.to_datetime(pags["Data de Pagamento"])
        pags["Valor_Depositado"] = pags["Valor Depositado"].astype(float)
        pags = pags.sort_values("data_pagamento", kind="stable").reset_index(drop=True)
        pags["ordem_pagamento"] = range(1, len(pags) + 1)
        if (pags["data_pagamento"].apply(lambda d: d.replace(day=1)) < data_inicial).any():
            erros.append(f"Há pagamento anterior à data-base inicial ({data_inicial:%m/%Y}).")
        if (pags["data_pagamento"].apply(lambda d: d.replace(day=1)) > data_final_ts).any():
            erros.append("Há pagamento posterior à data final da dívida.")

    if erros:
        for e in erros:
            st.error(e)
        st.session_state.pop("resultado", None)
    else:
        df_final = processar_esteira_completa(
            pags[["ordem_pagamento", "data_pagamento", "Valor_Depositado"]],
            principal, juros, data_inicial, fim_graca, data_final_ts, bases)

        parametros = {
            "Ano da proposta": ano_proposta,
            "Data-base inicial": data_inicial.strftime("%d/%m/%Y"),
            "Fim do período de graça": fim_graca.strftime("%d/%m/%Y"),
            "Data final da dívida": data_final_ts.strftime("%d/%m/%Y"),
            "Valor principal inicial": float(principal),
            "Juros iniciais": float(juros),
        }
        st.session_state["resultado"] = {
            "df": df_final,
            "parametros": parametros,
            "excel": gerar_excel(df_final, parametros, pags),
            "csv": gerar_csv(df_final),
            "aviso_indice": data_final_ts > ultima_data_comum,
        }

# ------------------------------------------------------------------------------
# Resultado (fica em session_state para não sumir ao clicar em Download)
# ------------------------------------------------------------------------------
res = st.session_state.get("resultado")
if res:
    st.divider()
    p = res["parametros"]
    st.subheader("Resultado")
    st.caption(f"Proposta {p['Ano da proposta']} · data-base {p['Data-base inicial']} · "
               f"fim da graça {p['Fim do período de graça']} · data final {p['Data final da dívida']}")

    if res["aviso_indice"]:
        st.warning(f"A data final é posterior ao último índice disponível em todas as bases "
                   f"({ultima_data_comum:%m/%Y}). Para os meses sem índice foi usado o último valor existente.")

    ultima = res["df"].iloc[-1]
    m1, m2, m3 = st.columns(3)
    fmt = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    m1.metric("Saldo principal", fmt(ultima["Saldo_Principal"]))
    m2.metric("Saldo juros", fmt(ultima["Saldo_Juros"]))
    m3.metric("Saldo total", fmt(ultima["Saldo_Total"]))

    st.dataframe(tabela_para_tela(res["df"]), use_container_width=True, hide_index=True)

    nome_base = f"RELATORIO-FINAL-UNIFICADO-{p['Ano da proposta']}"
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Baixar Excel (.xlsx)", res["excel"], file_name=f"{nome_base}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       type="primary", use_container_width=True)
    d2.download_button("⬇️ Baixar CSV (formato atual)", res["csv"], file_name=f"{nome_base}.csv",
                       mime="text/csv", use_container_width=True)

