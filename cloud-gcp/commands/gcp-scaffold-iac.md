---
description: Scaffold a Google Cloud Infrastructure-as-Code project — Terraform (primary) or Config Connector for GKE-centric teams, with opinionated production-grade defaults.
argument-hint: <workload-description>
---

# GCP Scaffold IaC

Scaffold a new Google Cloud Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the choice of tool.** Recommend based on the workload description, then defer to the user:
   - Most teams, especially multi-cloud or new to GCP → **Terraform** with `hashicorp/google` ≥ 5.x. Best ecosystem, most community modules, works alongside non-GCP providers.
   - Platform team using GKE as the control plane for everything → **Config Connector (KCC)**. GKE is a required prerequisite; KCC reconciles GCP resources from Kubernetes manifests.
   - Team with an existing large Deployment Manager investment and no migration capacity → **Cloud Deployment Manager** (maintenance mode; migrate eventually).
   Don't prescribe — recommend, then wait for the user's choice.

2. **Confirm scope** with up to three questions if not clear from the description:
   - Single project or multi-project (folder hierarchy, Shared VPC)?
   - Greenfield or migrating existing console-built resources (import vs fresh)?
   - Target region(s) and any compliance requirements that constrain resource location?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user names). Every scaffold includes:
   - Pinned provider / tool versions and a lockfile.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote state in a GCS bucket.
   - A `.gitignore` for the tool.
   - A `README.md` with bootstrap and deploy/destroy commands.
   - At minimum: a network module (VPC, subnets, Cloud NAT, Private Google Access), a compute placeholder, and a data placeholder.
   - CI with Workload Identity Federation (no service-account key files) for plan and apply.
   - Shared labels module / block (`environment`, `service`, `owner`, `cost_center`) applied to all resources.

4. **Wire safe defaults** in every scaffold:
   - Encryption at rest on all data stores — CMEK with a Cloud KMS key where supported.
   - Stateful resources tagged with `lifecycle { prevent_destroy = true }` in prod workspaces.
   - Private-by-default: Cloud SQL private IP only; GKE private cluster; Cloud Run `internal-and-cloud-load-balancing` ingress with a Load Balancer in front.
   - No service-account key files anywhere.
   - Cloud Logging log groups / sinks with bounded retention.
   - Labels block applied via a shared `locals.tf`.

5. **Print next steps** — the specific commands the user must run to bootstrap (enable APIs, create the Terraform state bucket, set up Workload Identity Federation), plus an explicit reminder that the first deploy goes to `dev`, not `prod`.

## Tool-specific layouts

### Terraform (HCL) — primary recommendation

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf         # GCS backend, CMEK-encrypted bucket
│   │   ├── main.tf            # Module instantiation for dev
│   │   ├── terraform.tfvars   # Dev-specific variable values (no secrets)
│   │   └── outputs.tf
│   ├── stage/
│   │   └── … (same shape)
│   └── prod/
│       └── … (same shape)
├── modules/
│   ├── network/
│   │   ├── main.tf            # google_compute_network, google_compute_subnetwork,
│   │   │                      # google_compute_router, google_compute_router_nat
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/
│   │   ├── main.tf            # Cloud Run service or GKE cluster placeholder
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── data/
│       ├── main.tf            # Cloud SQL instance or Firestore or Cloud Storage bucket
│       │                      # with prevent_destroy = true
│       ├── variables.tf
│       └── outputs.tf
├── shared/
│   └── locals.tf              # Common labels block
├── .terraform.lock.hcl        # Checked in; pins provider versions
├── .github/
│   └── workflows/
│       ├── tf-plan.yml        # Triggered on PR; WIF auth; posts plan as comment
│       └── tf-apply.yml       # Triggered on merge to main (dev/stage); manual approval for prod
├── .gitignore                 # .terraform/, *.tfstate, *.tfstate.backup, crash.log
└── README.md
```

#### Terraform GCS backend (example, `envs/dev/backend.tf`)

```hcl
terraform {
  backend "gcs" {
    bucket = "<project-id>-tfstate-dev"
    prefix = "terraform/state"
  }
}
```

The state bucket must be created before `terraform init` — script this in a `bootstrap/` directory or a `Makefile` target. Apply CMEK to the bucket: `google_storage_bucket` with `default_kms_key_name`.

#### Workload Identity Federation for GitHub Actions (example, `modules/ci-wif/main.tf`)

```hcl
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions pool"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "attribute.repository == \"<your-org>/<your-repo>\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
```

Grant the pool provider `roles/iam.workloadIdentityUser` on the Terraform CI service account scoped to the specific repository principal.

### Config Connector (KCC) — for GKE-centric platforms

```
.
├── config/
│   ├── network/
│   │   ├── computenetwork.yaml          # custom.googleapis.com/v1beta1 ComputeNetwork
│   │   ├── computesubnetwork-app.yaml
│   │   └── computerouternat.yaml
│   ├── data/
│   │   ├── sqldatabaseinstance.yaml     # SQLDatabaseInstance (Cloud SQL)
│   │   ├── storagebucket-assets.yaml
│   │   └── storagebucketiampolicy.yaml
│   ├── compute/
│   │   ├── containercluster.yaml        # ContainerCluster (GKE)
│   │   └── cloudrunservice.yaml
│   └── iam/
│       ├── iamserviceaccount-app.yaml
│       └── iampartialpolicy-app.yaml
├── overlays/
│   ├── dev/
│   │   └── kustomization.yaml           # Dev-specific patches (smaller SQL tier, etc.)
│   ├── stage/
│   │   └── kustomization.yaml
│   └── prod/
│       └── kustomization.yaml
├── .github/
│   └── workflows/
│       └── kcc-apply.yml                # gcloud auth via WIF; kubectl apply -k overlays/<env>
└── README.md
```

KCC prerequisites:
- A GKE cluster with Config Connector add-on enabled (`addonsConfig.configConnectorConfig.enabled = true`).
- The KCC controller's Kubernetes service account annotated with a GCP service account that has the required IAM roles.
- Namespace-scoped mode: each namespace targets a different GCP project via a `ConfigConnectorContext` resource.

## After scaffolding

- Hand off to the `gcp-architect` sub-agent for a same-day review before the first `terraform apply` or `kubectl apply`.
- Run `gcp-security-reviewer` once the `dev` environment is deployed, before any traffic reaches the workload.
- Ensure the state bucket, KMS key ring, and Workload Identity pool are created in a `bootstrap/` step that runs exactly once — separate these from the regularly-applied modules.
- Remind the user: enabling GCP APIs (`google_project_service`) is idempotent but takes 30–90 seconds on first apply. Run the network module first; compute and data modules depend on APIs being fully active.
