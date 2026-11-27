"""ETL - Etapa 2: carrega o parquet agregado no Aiven for PostgreSQL.

Uso:
    export DATABASE_URL="postgres://avnadmin:SENHA@HOST:PORTA/defaultdb?sslmode=require"
    python etl/load_postgres.py
A URL vem do 'terraform output -raw pg_service_uri' (nunca fica no codigo).
"""
import argparse, io, os, sys
import duckdb, psycopg2

COLS = ["data_base","uf","regiao","segmento","cliente","porte","modalidade","origem",
        "perfil_microcredito","n_registros","numero_operacoes","carteira_ativa",
        "carteira_inadimplencia","ativo_problematico","carteira_vencida"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default="data/scr_agregado.parquet")
    ap.add_argument("--schema", default="sql/schema.sql")
    ap.add_argument("--ibge", default="data/ibge_familias_uf.csv")
    a = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Defina DATABASE_URL (veja README, passo 4).")
    if not os.path.exists(a.parquet):
        sys.exit(f"{a.parquet} nao existe. Rode primeiro etl/transform.py")

    buf = io.StringIO()
    df = duckdb.connect().execute(f"SELECT {', '.join(COLS)} FROM '{a.parquet}' ORDER BY data_base, uf").df()
    df["numero_operacoes"] = df["numero_operacoes"].astype("Int64")  # evita "123.0" no COPY
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(open(a.schema, encoding="utf-8").read())
        cur.execute("TRUNCATE fato_credito RESTART IDENTITY")  # idempotente: pode rodar de novo
        cur.copy_expert(
            f"COPY fato_credito ({', '.join(COLS)}) FROM STDIN WITH (FORMAT csv)", buf)
        cur.execute("SELECT COUNT(*), pg_size_pretty(pg_total_relation_size('fato_credito')) FROM fato_credito")
        n, size = cur.fetchone()
        # recorte de gênero x raça (IBGE Censo 2022), gerado por etl/ibge_censo.py
        n_ibge = 0
        if os.path.exists(a.ibge):
            cur.execute("TRUNCATE ibge_familias_uf")
            with open(a.ibge, encoding="utf-8") as f:
                cur.copy_expert(
                    "COPY ibge_familias_uf (uf, sexo, cor_raca, familias) FROM STDIN WITH (FORMAT csv, HEADER true)", f)
            cur.execute("SELECT COUNT(*) FROM ibge_familias_uf")
            n_ibge = cur.fetchone()[0]
    print(f"OK: {n:,} linhas carregadas ({size} usados no Aiven)")
    print(f"OK: {n_ibge} linhas do IBGE em ibge_familias_uf" if n_ibge else
          f"Aviso: {a.ibge} nao encontrado; rode etl/ibge_censo.py para o recorte de genero x raca")

if __name__ == "__main__":
    main()
