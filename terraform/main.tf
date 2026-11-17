terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = ">= 4.0.0, < 5.0.0"
    }
  }
}

# O token NAO fica no codigo: use a variavel de ambiente TF_VAR_aiven_api_token
provider "aiven" {
  api_token = var.aiven_api_token
}

# PostgreSQL gratuito (1 GB) - banco principal do projeto
resource "aiven_pg" "microcredito" {
  project      = var.aiven_project_name
  service_name = var.service_name
  cloud_name   = var.cloud_name
  plan         = var.pg_plan # free tier

  termination_protection = false
  # Sem pg_version fixa: o plano Free nao permite escolher versao (a Aiven usa a padrao, hoje PostgreSQL 18)
}

# Banco de dados logico do projeto
resource "aiven_pg_database" "scr" {
  project       = var.aiven_project_name
  service_name  = aiven_pg.microcredito.service_name
  database_name = "scr_microcredito"
}

# Usuario dedicado ao dashboard (as permissoes de leitura sao concedidas em sql/grants.sql)
resource "aiven_pg_user" "dashboard" {
  project      = var.aiven_project_name
  service_name = aiven_pg.microcredito.service_name
  username     = "dashboard_ro"
}
