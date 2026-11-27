"""Dashboard - Acesso a Microcrédito e Inclusão Financeira Regional (SCR/BCB 2025).

Lê do Aiven PostgreSQL (st.secrets['DATABASE_URL'] ou env DATABASE_URL).
Sem URL configurada, ou se o banco estiver indisponível, usa os arquivos locais
da pasta data/ (modo demonstração/offline).
"""
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Microcrédito e Inclusão Financeira", layout="wide")

PASTA_DADOS = os.path.join(os.path.dirname(__file__), "..", "data")

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
    "grupo": "Pessoa responsável pela família",
    "pct_familias": "% das famílias",
    "pct_mulher_negra": "% de famílias chefiadas por mulheres negras",
}


def br(valor, casas=1):
    """Formata número no padrão brasileiro: 7.444,3"""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def grafico(fig):
    """Exibe o gráfico com vírgula decimal e ponto de milhar (padrão brasileiro)."""
    fig.update_layout(separators=",.")
    st.plotly_chart(fig, width="stretch")


def get_url():
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.environ.get("DATABASE_URL")


@st.cache_data(ttl=3600, show_spinner="Consultando base...")
def consultar_banco(sql):
    """Consulta o Aiven. Se falhar, a exceção não fica em cache e a próxima visita tenta de novo."""
    import psycopg2
    with psycopg2.connect(get_url(), connect_timeout=10) as conn:
        return pd.read_sql(sql, conn)


@st.cache_data(show_spinner="Lendo dados locais...")
def ler_parquet():
    import duckdb
    path = os.path.join(PASTA_DADOS, "scr_agregado.parquet")
    return duckdb.connect().execute(f"SELECT * FROM '{path}'").df()


def carregar():
    origem = "parquet local (modo demonstração)"
    df = None
    if get_url():
        try:
            df = consultar_banco("SELECT * FROM fato_credito")
            origem = "Aiven PostgreSQL"
        except Exception:
            origem = "parquet local (o banco da Aiven não respondeu)"
    if df is None:
        df = ler_parquet()
    df = df.copy()
    df["data_base"] = pd.to_datetime(df["data_base"])
    for c in ["carteira_ativa", "carteira_inadimplencia", "ativo_problematico", "carteira_vencida"]:
        df[c] = df[c].astype(float)
    # o ETL antigo gravou este rótulo sem acento; corrige na exibição
    for c in ["regiao", "porte"]:
        df[c] = df[c].replace("Nao informado", "Não informado")
    df["perfil"] = df["perfil_microcredito"].map({True: "Perfil microcrédito", False: "Demais"})
    return df, origem


def carregar_ibge():
    """Famílias por sexo e cor ou raça da pessoa responsável, por UF (IBGE Censo 2022)."""
    if get_url():
        try:
            return consultar_banco("SELECT uf, sexo, cor_raca, familias FROM ibge_familias_uf")
        except Exception:
            pass  # tabela ainda não carregada ou banco fora do ar: usa o CSV do repositório
    path = os.path.join(PASTA_DADOS, "ibge_familias_uf.csv")
    return pd.read_csv(path) if os.path.exists(path) else None


df, origem = carregar()
ibge = carregar_ibge()

st.title("Acesso a Microcrédito e Inclusão Financeira Regional")
st.caption(f"Fonte: SCR - Banco Central do Brasil (dados abertos), 2025 e IBGE - Censo 2022 | Conectado a: {origem}")

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

# ---------- métricas analíticas ----------
st.subheader("1. Distribuição regional do crédito")
reg = snap.groupby(["regiao", "perfil"], as_index=False)["carteira_ativa"].sum()
reg["R$ bi"] = reg["carteira_ativa"] / 1e9
grafico(px.bar(reg, x="regiao", y="R$ bi", color="perfil", barmode="group", labels=ROTULOS))

st.subheader("2. Inadimplência por região: perfil microcrédito x demais (interseção regional x demográfica)")
t = snap.groupby(["regiao", "perfil"]).apply(taxa, include_groups=False).reset_index(name="inadimplencia_%")
grafico(px.bar(t, x="regiao", y="inadimplencia_%", color="perfil", barmode="group", labels=ROTULOS))

st.subheader("3. Crédito por UF - participação do perfil microcrédito")
uf = snap.groupby("uf").apply(
    lambda d: pd.Series({
        "carteira_bi": d["carteira_ativa"].sum() / 1e9,
        "pct_micro": 100 * d[d["perfil_microcredito"]]["carteira_ativa"].sum() / d["carteira_ativa"].sum()}),
    include_groups=False).reset_index().sort_values("pct_micro", ascending=False)
grafico(px.bar(uf, x="uf", y="pct_micro", color="carteira_bi", labels=ROTULOS))

st.subheader("4. Evolução mensal da carteira (R$ bi)")
ev = f.groupby(["data_base", "perfil"], as_index=False)["carteira_ativa"].sum()
ev["R$ bi"] = ev["carteira_ativa"] / 1e9
grafico(px.line(ev, x="data_base", y="R$ bi", color="perfil", markers=True, labels=ROTULOS))

c1, c2 = st.columns(2)
with c1:
    st.subheader("5. Carteira por porte / faixa de renda")
    p = snap.groupby("porte", as_index=False)["carteira_ativa"].sum().sort_values("carteira_ativa")
    p["R$ bi"] = p["carteira_ativa"] / 1e9
    grafico(px.bar(p, x="R$ bi", y="porte", orientation="h", labels=ROTULOS))
with c2:
    st.subheader("6. Quem empresta: segmento da instituição")
    s = snap[snap["perfil_microcredito"]].groupby("segmento", as_index=False)["carteira_ativa"].sum()
    grafico(px.pie(s, names="segmento", values="carteira_ativa", hole=0.4, labels=ROTULOS))

# ---------- recorte interseccional gênero x raça (ODS 5 e 18) ----------
st.subheader("7. Gênero x raça (ODS 5 e 18): perfil das famílias e acesso ao microcrédito por UF")
if ibge is None or ibge.empty:
    st.info("Dados do IBGE não encontrados. Rode `python etl/ibge_censo.py` para gerar data/ibge_familias_uf.csv.")
else:
    ib = ibge[ibge["uf"].isin(ufs)].copy()
    negra = ib["cor_raca"].isin(["Preta", "Parda"])
    branca = ib["cor_raca"].eq("Branca")
    mulher = ib["sexo"].eq("Mulheres")
    ib["grupo"] = "Outras (amarela, indígena, sem declaração)"
    ib.loc[mulher & negra, "grupo"] = "Mulher negra"
    ib.loc[mulher & branca, "grupo"] = "Mulher branca"
    ib.loc[~mulher & negra, "grupo"] = "Homem negro"
    ib.loc[~mulher & branca, "grupo"] = "Homem branco"

    comp = ib.groupby(["uf", "grupo"], as_index=False)["familias"].sum()
    comp["pct_familias"] = 100 * comp["familias"] / comp.groupby("uf")["familias"].transform("sum")
    pct_mn = (comp[comp["grupo"] == "Mulher negra"].set_index("uf")["pct_familias"]
              .rename("pct_mulher_negra").reset_index())

    total_fam = ib["familias"].sum()
    m1, m2, m3 = st.columns(3)
    m1.metric("Famílias chefiadas por mulheres", f"{br(100 * ib[mulher]['familias'].sum() / total_fam, 1)}%")
    m2.metric("Famílias chefiadas por pessoas negras", f"{br(100 * ib[negra]['familias'].sum() / total_fam, 1)}%")
    m3.metric("Famílias chefiadas por mulheres negras", f"{br(100 * ib[mulher & negra]['familias'].sum() / total_fam, 1)}%")

    ordem = pct_mn.sort_values("pct_mulher_negra", ascending=False)["uf"].tolist()
    grafico(px.bar(comp, x="uf", y="pct_familias", color="grupo", labels=ROTULOS,
                   category_orders={"uf": ordem, "grupo": ["Mulher negra", "Mulher branca", "Homem negro",
                                                           "Homem branco", "Outras (amarela, indígena, sem declaração)"]},
                   title="Quem chefia as famílias em cada UF (IBGE, Censo 2022)"))

    cruz = uf.merge(pct_mn, on="uf")
    fig = px.scatter(cruz, x="pct_mulher_negra", y="pct_micro", size="carteira_bi", text="uf",
                     labels=ROTULOS, title="Estados com mais famílias chefiadas por mulheres negras x "
                                           "participação do microcrédito na carteira")
    fig.update_traces(textposition="top center")
    grafico(fig)
    if len(cruz) >= 3:
        r = cruz["pct_mulher_negra"].corr(cruz["pct_micro"])
        st.caption(f"Correlação entre as duas medidas nas UFs selecionadas: r = {br(r, 2)}. "
                   "Análise por estado (ecológica): o SCR não informa sexo nem raça de quem toma o crédito, "
                   "então o cruzamento é feito pelo perfil das famílias de cada UF. Correlação não indica causa.")

with st.expander("Limitações metodológicas (leia)"):
    st.markdown(
        "- A base pública do SCR **não traz sexo nem raça/cor** do tomador; o recorte demográfico do crédito usa **PF/PJ, porte e faixa de renda**.\n"
        "- O recorte de **gênero x raça** (seção 7) vem do **IBGE, Censo 2022 (tabela 10176)** e é cruzado com o crédito **por UF**: mostra onde há mais famílias chefiadas por mulheres negras, não quem recebeu cada empréstimo.\n"
        "- 'Perfil microcrédito' é uma **aproximação** (não há campo oficial de microcrédito nesta base).\n"
        "- Valores de `numero_de_operacoes` = -1 são sigilosos no original e foram tratados como nulos.")
