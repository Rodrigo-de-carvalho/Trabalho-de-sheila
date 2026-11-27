"""Dashboard - Acesso a Microcrédito e Inclusão Financeira Regional (SCR/BCB 2025).

Lê do Aiven PostgreSQL (st.secrets['DATABASE_URL'] ou env DATABASE_URL).
Sem URL configurada, usa o parquet local (modo demonstração/offline).
"""
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Microcrédito e Inclusão Financeira", layout="wide")

# Nomes exibidos nos eixos e legendas dos gráficos (em vez dos nomes técnicos das colunas)
ROTULOS = {
    "regiao": "Região",
    "perfil": "Perfil",
    "uf": "UF",
    "porte": "Porte / faixa de renda",
    "segmento": "Segmento",
    "data_base": "Mês",
    "R$ bi": "R$ bi",
    "inadimplencia_%": "Inadimplência (%)",
    "pct_micro": "% da carteira em perfil microcrédito",
    "carteira_bi": "Carteira (R$ bi)",
    "carteira_ativa": "Carteira ativa (R$)",
}


def br(valor, casas=1):
    """Formata número no padrão brasileiro: 7.444,3"""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_url():
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.environ.get("DATABASE_URL")


@st.cache_data(ttl=3600, show_spinner="Consultando base...")
def carregar():
    url = get_url()
    if url:
        import psycopg2
        with psycopg2.connect(url) as conn:
            df = pd.read_sql("SELECT * FROM fato_credito", conn)
        origem = "Aiven PostgreSQL"
    else:
        import duckdb
        path = os.path.join(os.path.dirname(__file__), "..", "data", "scr_agregado.parquet")
        df = duckdb.connect().execute(f"SELECT * FROM '{path}'").df()
        origem = "parquet local (modo demonstração)"
    df["data_base"] = pd.to_datetime(df["data_base"])
    for c in ["carteira_ativa", "carteira_inadimplencia", "ativo_problematico", "carteira_vencida"]:
        df[c] = df[c].astype(float)
    # o ETL gravou este rótulo sem acento; corrige na exibição
    for c in ["regiao", "porte"]:
        df[c] = df[c].replace("Nao informado", "Não informado")
    df["perfil"] = df["perfil_microcredito"].map({True: "Perfil microcrédito", False: "Demais"})
    return df, origem


df, origem = carregar()

st.title("Acesso a Microcrédito e Inclusão Financeira Regional")
st.caption(f"Fonte: SCR - Banco Central do Brasil (dados abertos), 2025 | Conectado a: {origem}")

# ---------- filtros dinâmicos ----------
with st.sidebar:
    st.header("Filtros")
    meses = sorted(df["data_base"].dt.strftime("%Y-%m").unique())
    m_ini, m_fim = st.select_slider("Período", options=meses, value=(meses[0], meses[-1]))
    regioes = st.multiselect("Região", sorted(df["regiao"].unique()), default=sorted(df["regiao"].unique()))
    ufs_disp = sorted(df[df["regiao"].isin(regioes)]["uf"].unique())
    ufs = st.multiselect("UF", ufs_disp, default=ufs_disp)
    cliente = st.multiselect("Tipo de cliente", ["PF", "PJ"], default=["PF", "PJ"])
    segmentos = st.multiselect("Segmento da instituição", sorted(df["segmento"].unique()),
                               default=sorted(df["segmento"].unique()))
    so_micro = st.checkbox("Somente perfil de microcrédito", value=False)
    st.info("Perfil microcrédito (proxy): PJ micro/pequena empresa ou PF com renda até 2 salários mínimos / sem rendimento.")

mes = df["data_base"].dt.strftime("%Y-%m")
f = df[(mes >= m_ini) & (mes <= m_fim) & df["regiao"].isin(regioes) & df["uf"].isin(ufs)
       & df["cliente"].isin(cliente) & df["segmento"].isin(segmentos)]
if so_micro:
    f = f[f["perfil_microcredito"]]
if f.empty:
    st.warning("Nenhum dado para os filtros escolhidos.")
    st.stop()

ult = f["data_base"].max()
snap = f[f["data_base"] == ult]   # carteira e saldo (estoque): usa o último mês do período


def taxa(d):
    return 100 * d["carteira_inadimplencia"].sum() / d["carteira_ativa"].sum() if d["carteira_ativa"].sum() else 0


k1, k2, k3, k4 = st.columns(4)
k1.metric("Carteira ativa (R$ bi)", br(snap["carteira_ativa"].sum() / 1e9, 1))
share = 100 * snap[snap["perfil_microcredito"]]["carteira_ativa"].sum() / snap["carteira_ativa"].sum()
k2.metric("% carteira em perfil microcrédito", f"{br(share, 1)}%")
k3.metric("Inadimplência (>90 dias)", f"{br(taxa(snap), 2)}%")
k4.metric("Inadimplência perfil microcrédito", f"{br(taxa(snap[snap['perfil_microcredito']]), 2)}%")
st.caption(f"Indicadores de estoque referem-se a {ult:%m/%Y} (último mês do período selecionado).")

# ---------- 4+ métricas analíticas ----------
st.subheader("1. Distribuição regional do crédito")
reg = snap.groupby(["regiao", "perfil"], as_index=False)["carteira_ativa"].sum()
reg["R$ bi"] = reg["carteira_ativa"] / 1e9
st.plotly_chart(px.bar(reg, x="regiao", y="R$ bi", color="perfil", barmode="group", labels=ROTULOS),
                width="stretch")

st.subheader("2. Inadimplência por região: perfil microcrédito x demais (interseção regional x demográfica)")
t = snap.groupby(["regiao", "perfil"]).apply(taxa, include_groups=False).reset_index(name="inadimplencia_%")
st.plotly_chart(px.bar(t, x="regiao", y="inadimplencia_%", color="perfil", barmode="group", labels=ROTULOS),
                width="stretch")

st.subheader("3. Crédito por UF - participação do perfil microcrédito")
uf = snap.groupby("uf").apply(
    lambda d: pd.Series({
        "carteira_bi": d["carteira_ativa"].sum() / 1e9,
        "pct_micro": 100 * d[d["perfil_microcredito"]]["carteira_ativa"].sum() / d["carteira_ativa"].sum()}),
    include_groups=False).reset_index().sort_values("pct_micro", ascending=False)
st.plotly_chart(px.bar(uf, x="uf", y="pct_micro", color="carteira_bi", labels=ROTULOS), width="stretch")

st.subheader("4. Evolução mensal da carteira (R$ bi)")
ev = f.groupby(["data_base", "perfil"], as_index=False)["carteira_ativa"].sum()
ev["R$ bi"] = ev["carteira_ativa"] / 1e9
st.plotly_chart(px.line(ev, x="data_base", y="R$ bi", color="perfil", markers=True, labels=ROTULOS),
                width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.subheader("5. Carteira por porte / faixa de renda")
    p = snap.groupby("porte", as_index=False)["carteira_ativa"].sum().sort_values("carteira_ativa")
    p["R$ bi"] = p["carteira_ativa"] / 1e9
    st.plotly_chart(px.bar(p, x="R$ bi", y="porte", orientation="h", labels=ROTULOS), width="stretch")
with c2:
    st.subheader("6. Quem empresta: segmento da instituição")
    s = snap[snap["perfil_microcredito"]].groupby("segmento", as_index=False)["carteira_ativa"].sum()
    st.plotly_chart(px.pie(s, names="segmento", values="carteira_ativa", hole=0.4, labels=ROTULOS),
                    width="stretch")

with st.expander("Limitações metodológicas (leia)"):
    st.markdown(
        "- A base pública do SCR **não traz sexo nem raça/cor** do tomador; o recorte demográfico usa **PF/PJ, porte e faixa de renda**.\n"
        "- 'Perfil microcrédito' é uma **aproximação** (não há campo oficial de microcrédito nesta base).\n"
        "- Valores de `numero_de_operacoes` = -1 são sigilosos no original e foram tratados como nulos.")
