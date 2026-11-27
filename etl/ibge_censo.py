"""ETL - Etapa 1b: baixa do IBGE (Censo 2022) as famílias por sexo e cor ou raça
da pessoa responsável, por UF. É o recorte de gênero x raça (ODS 5 e 18) que a
base do SCR não tem.

Fonte oficial: IBGE/SIDRA, tabela 10176 (Censo Demográfico 2022)
https://sidra.ibge.gov.br/tabela/10176

Uso:
    python etl/ibge_censo.py --output data/ibge_familias_uf.csv

Tratamentos:
  * código IBGE da UF -> sigla (para cruzar com o SCR, que usa a sigla);
  * "-" / "..." do SIDRA (valor inexistente ou sigiloso) -> 0;
  * mantém só os totais de número de componentes e de nível de instrução.
"""
import argparse
import csv
import json
import os
import urllib.request

URL = (
    "https://apisidra.ibge.gov.br/values/t/10176/n3/all/v/1677/p/2022"
    "/c12088/9963"            # número de componentes: total
    "/c11807/95418,95419"     # sexo da pessoa responsável: homens, mulheres
    "/c12252/104809,104810,104811,104812,104813,104814"  # cor ou raça (sem o total)
    "/c512/77735"             # nível de instrução: total
    "?formato=json"
)

UF_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def baixar():
    req = urllib.request.Request(URL, headers={"User-Agent": "projeto-academico-microcredito"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        linhas = json.load(resp)
    cab, dados = linhas[0], linhas[1:]
    col = {v: k for k, v in cab.items()}  # nome da coluna -> chave (D1C, D4N...)
    saida = []
    for r in dados:
        valor = r["V"]
        saida.append({
            "uf": UF_SIGLA[r[col["Unidade da Federação (Código)"]]],
            "sexo": r[col["Sexo da pessoa responsável pela família"]],
            "cor_raca": r[col["Cor ou raça da pessoa responsável pela família"]],
            "familias": int(valor) if valor.isdigit() else 0,
        })
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="data/ibge_familias_uf.csv")
    a = ap.parse_args()
    linhas = baixar()
    os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["uf", "sexo", "cor_raca", "familias"])
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda r: (r["uf"], r["sexo"], r["cor_raca"])))
    total = sum(r["familias"] for r in linhas)
    print(f"OK: {len(linhas)} linhas ({total:,} famílias) -> {a.output}")


if __name__ == "__main__":
    main()
