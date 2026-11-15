variable "aiven_api_token" {
  description = "Token de API da Aiven (use TF_VAR_aiven_api_token, nunca commite)"
  type        = string
  sensitive   = true
}

variable "aiven_project_name" {
  description = "Nome do projeto na console da Aiven"
  type        = string
}

variable "service_name" {
  description = "Nome do servico PostgreSQL"
  type        = string
  default     = "pg-microcredito"
}

variable "cloud_name" {
  description = "Cloud/regiao. O free tier so existe em algumas regioes - confira na console"
  type        = string
  default     = "google-europe-west1"
}

variable "pg_plan" {
  description = "Plano do PostgreSQL. Gratuito: free-1-1gb (confira o nome atual na console)"
  type        = string
  default     = "free-1-1gb"
}
