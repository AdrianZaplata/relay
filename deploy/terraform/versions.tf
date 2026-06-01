# Authored against the official STACKIT Terraform provider (stackitcloud/stackit).
# This is illustrative infrastructure-as-code: it is NOT applied in this build, and
# argument names should be pinned/verified against the provider version in use.
# The point is to show the platform's managed services modelled as code, the way
# Terraform/Terragrunt would provision them on STACKIT.

terraform {
  required_version = ">= 1.7"

  required_providers {
    stackit = {
      source  = "stackitcloud/stackit"
      version = "~> 0.40"
    }
  }

  # State lives in STACKIT Object Storage (S3-compatible) in production, so it's
  # shared and locked — never on a laptop. Terragrunt would generate this block.
  backend "s3" {
    # bucket / key / endpoints provided by Terragrunt per environment
  }
}

provider "stackit" {
  region = var.region
  # Auth via the STACKIT_SERVICE_ACCOUNT_TOKEN env var (a service-account key),
  # injected at runtime by CI — never committed.
}
