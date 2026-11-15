output "pg_service_uri" {
  description = "URI de conexao (admin) para o ETL: terraform output -raw pg_service_uri"
  value       = aiven_pg.microcredito.service_uri
  sensitive   = true
}

output "pg_host" {
  value = aiven_pg.microcredito.service_host
}

output "pg_port" {
  value = aiven_pg.microcredito.service_port
}
