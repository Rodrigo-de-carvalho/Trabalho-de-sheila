-- Opcional: rode como admin apos a carga para o dashboard usar um usuario somente-leitura
GRANT CONNECT ON DATABASE defaultdb TO dashboard_ro;
GRANT USAGE ON SCHEMA public TO dashboard_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_ro;
