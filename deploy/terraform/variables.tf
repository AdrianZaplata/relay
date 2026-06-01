variable "project_id" {
  description = "STACKIT project (resource container) ID"
  type        = string
}

variable "region" {
  description = "STACKIT region"
  type        = string
  default     = "eu01"
}

variable "environment" {
  description = "Deployment environment (per-env workspace via Terragrunt)"
  type        = string
  default     = "dev"
}

variable "kubernetes_version" {
  description = "SKE Kubernetes minor version"
  type        = string
  default     = "1.30"
}
