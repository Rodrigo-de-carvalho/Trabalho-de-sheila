"""ETL - Etapa 1: le os CSVs do SCR (Banco Central), limpa e agrega.

Uso:
    python etl/transform.py --input CAMINHO_DOS_CSVS --output data/scr_agregado.parquet

Tratamentos aplicados (criterio "qualidade do ETL"):
  * tipagem: datas -> DATE, valores com virgula decimal -> DOUBLE
  * nulos: numero_de_operacoes = -1 (dado sigiloso/mascarado pelo BCB) vira NULL;
           'Indisponivel' em porte vira 'Nao informado'
  * enriquecimento: UF -> regiao, faixa de renda/porte unificada, flag de microcredito (proxy)
  * agregacao: remove cnae/submodalidade/indexador para caber nos 1 GB do plano free
"""
import argparse
import glob
import os
import duckdb

REGIOES = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MT", "MS"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}

def build_sql(files_glob: str) -> str:
    regiao_case = "CASE uf " + " ".join(
        f"WHEN '{u}' THEN '{r}'" for r, ufs in REGIOES.items() for u in ufs
    ) + " ELSE 'Nao informado' END"
    num = lambda c: f"COALESCE(TRY_CAST(REPLACE({c}, ',', '.') AS DOUBLE), 0)"
    return f"""
    WITH raw AS (
        SELECT * FROM read_csv('{files_glob}', delim=';', header=true,
                               all_varchar=true, quote='"', encoding='utf-8')
    )
    SELECT
        CAST(data_base AS DATE)                                   AS data_base,
        uf,
        {regiao_case}                                             AS regiao,
        segmento,
        cliente,
        CASE WHEN porte LIKE 'Indispon%' THEN 'Nao informado' ELSE porte END AS porte,
        modalidade,
        origem,
        -- microcredito (proxy): PJ micro/pequena empresa ou PF ate 2 salarios minimos
        (  (cliente = 'PJ' AND porte IN ('Micro','Pequeno'))
        OR (cliente = 'PF' AND (porte LIKE 'At_ 1 sal%' OR porte LIKE 'Mais de 1 a 2 sal%' OR porte = 'Sem rendimento'))
        )                                                         AS perfil_microcredito,
        COUNT(*)                                                  AS n_registros,
        SUM(CASE WHEN TRY_CAST(numero_de_operacoes AS BIGINT) >= 0
                 THEN TRY_CAST(numero_de_operacoes AS BIGINT) END) AS numero_operacoes,
        SUM({num('carteira_ativa')})                              AS carteira_ativa,
        SUM({num('carteira_inadimplencia')})                      AS carteira_inadimplencia,
        SUM({num('ativo_problematico')})                          AS ativo_problematico,
        SUM({num('carteira_vencida')})                            AS carteira_vencida
    FROM raw
    GROUP BY ALL
    HAVING SUM({num('carteira_ativa')}) > 0
    """

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="pasta com scrdata_*.csv")
    ap.add_argument("--output", default="data/scr_agregado.parquet")
    a = ap.parse_args()
    pattern = os.path.join(a.input, "scrdata_*.csv").replace("\\", "/")
    if not glob.glob(pattern):
        raise SystemExit(f"Nenhum CSV encontrado em {pattern}")
    os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
    con = duckdb.connect()
    con.execute(f"COPY ({build_sql(pattern)}) TO '{a.output}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n = con.execute(f"SELECT COUNT(*) FROM '{a.output}'").fetchone()[0]
    print(f"OK: {n:,} linhas agregadas -> {a.output}")

if __name__ == "__main__":
    main()
