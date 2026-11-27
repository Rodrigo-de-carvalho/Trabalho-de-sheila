-- Modelagem do banco (Aiven for PostgreSQL free tier)
CREATE TABLE IF NOT EXISTS fato_credito (
    id                      BIGSERIAL PRIMARY KEY,
    data_base               DATE          NOT NULL,
    uf                      CHAR(2)       NOT NULL,
    regiao                  VARCHAR(20)   NOT NULL,
    segmento                VARCHAR(40)   NOT NULL,
    cliente                 CHAR(2)       NOT NULL CHECK (cliente IN ('PF','PJ')),
    porte                   VARCHAR(40)   NOT NULL,
    modalidade              VARCHAR(100)  NOT NULL,
    origem                  VARCHAR(40)   NOT NULL,
    perfil_microcredito     BOOLEAN       NOT NULL,
    n_registros             INTEGER       NOT NULL,
    numero_operacoes        BIGINT,                      -- NULL = dado sigiloso (-1 no original)
    carteira_ativa          NUMERIC(20,2) NOT NULL,
    carteira_inadimplencia  NUMERIC(20,2) NOT NULL,
    ativo_problematico      NUMERIC(20,2) NOT NULL,
    carteira_vencida        NUMERIC(20,2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fato_data     ON fato_credito (data_base);
CREATE INDEX IF NOT EXISTS idx_fato_uf       ON fato_credito (uf);
CREATE INDEX IF NOT EXISTS idx_fato_regiao   ON fato_credito (regiao);
CREATE INDEX IF NOT EXISTS idx_fato_micro    ON fato_credito (perfil_microcredito);

COMMENT ON TABLE  fato_credito IS 'SCR/Banco Central 2025, agregado por mes x UF x segmento x cliente x porte x modalidade x origem';
COMMENT ON COLUMN fato_credito.perfil_microcredito IS 'Proxy: PJ micro/pequena OU PF com renda ate 2 SM / sem rendimento';

-- Recorte de gênero x raça (ODS 5 e 18): IBGE Censo 2022, tabela 10176
CREATE TABLE IF NOT EXISTS ibge_familias_uf (
    uf        CHAR(2)      NOT NULL,
    sexo      VARCHAR(10)  NOT NULL CHECK (sexo IN ('Homens','Mulheres')),
    cor_raca  VARCHAR(20)  NOT NULL,
    familias  INTEGER      NOT NULL,
    PRIMARY KEY (uf, sexo, cor_raca)
);

COMMENT ON TABLE ibge_familias_uf IS 'IBGE Censo 2022 (tabela 10176): famílias por sexo e cor ou raça da pessoa responsável, por UF';
