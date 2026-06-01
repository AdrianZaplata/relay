# The platform's managed services, as code. Mirrors the live stack: a Kubernetes
# Engine cluster (SKE) runs the workloads; PostgreSQL Flex is the operational store;
# Object Storage is the telemetry data lake; Secrets Manager backs ExternalSecret
# Operator. Names follow an <app>-<env> convention for per-environment isolation.

locals {
  name = "relay-${var.environment}"
}

# --- Kubernetes Engine (SKE) -------------------------------------------------
resource "stackit_ske_cluster" "relay" {
  project_id         = var.project_id
  name               = local.name
  kubernetes_version = var.kubernetes_version

  node_pools = [
    {
      name               = "default"
      machine_type       = "g1.2"
      minimum            = 2
      maximum            = 4
      availability_zones = ["${var.region}-1", "${var.region}-2"]
      os_version_min     = "3815.2.5"
      volume_size        = 50
      volume_type        = "storage_premium_perf2"
    }
  ]

  maintenance = {
    enable_kubernetes_version_updates    = true
    enable_machine_image_version_updates = true
    start                                = "02:00:00Z"
    end                                  = "04:00:00Z"
  }
}

# --- PostgreSQL Flex (operational / hot store) -------------------------------
resource "stackit_postgresflex_instance" "relay" {
  project_id      = var.project_id
  name            = local.name
  version         = "16"
  flavor          = { cpu = 2, ram = 8 }
  replicas        = var.environment == "prod" ? 3 : 1
  storage         = { class = "premium-perf2-stackit", size = 20 }
  backup_schedule = "0 2 * * *"
  acl             = ["10.0.0.0/8"] # cluster CIDR only; not public
}

# --- Object Storage (telemetry data lake) ------------------------------------
resource "stackit_objectstorage_bucket" "data_lake" {
  project_id = var.project_id
  name       = "${local.name}-telemetry-lake"
}

# --- Secrets Manager (backs ExternalSecret Operator) -------------------------
resource "stackit_secretsmanager_instance" "relay" {
  project_id = var.project_id
  name       = local.name
}

output "kube_config_note" {
  value = "Fetch kubeconfig via the SKE credentials resource; ArgoCD then owns app delivery."
}

output "postgres_host" {
  value     = stackit_postgresflex_instance.relay.name
  sensitive = false
}
