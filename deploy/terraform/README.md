# STACKIT infrastructure as code (authored, not applied)

Illustrative Terraform for the platform's managed services on STACKIT:

| Resource | Maps to |
|---|---|
| `stackit_ske_cluster` | Kubernetes Engine — runs the workloads |
| `stackit_postgresflex_instance` | PostgreSQL Flex — operational hot store |
| `stackit_objectstorage_bucket` | Object Storage — telemetry data lake |
| `stackit_secretsmanager_instance` | Secrets Manager — backs ExternalSecret Operator |

## Honest scope

This is **authored and reviewed, not `terraform apply`-d** in this build. It exists to
show the managed stack modelled as code and the conventions I'd use. Provider argument
names should be pinned and verified against the `stackitcloud/stackit` version in
`versions.tf` before any real plan/apply.

## How it would run for real

- **Terragrunt** wraps this root module to keep it DRY across environments
  (`dev` / `staging` / `prod`), generating the backend + provider blocks and supplying
  per-env `*.tfvars`. No copy-pasted state config.
- **Remote state** in STACKIT Object Storage (S3-compatible), locked, shared.
- **CI** runs `terraform plan` on merge requests and `apply` on protected branches —
  infrastructure ships through the same review gate as application code.
- Separation of duties: Terraform provisions the *cluster and data services*; **ArgoCD**
  ([../argocd](../argocd)) owns *application delivery* onto the cluster. Two loops, one
  git source of truth.
