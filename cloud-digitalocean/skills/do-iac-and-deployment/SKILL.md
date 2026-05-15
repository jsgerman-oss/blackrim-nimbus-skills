---
name: do-iac-and-deployment
description: Choose, scaffold, or review DigitalOcean Infrastructure-as-Code and deployment — doctl CLI, Terraform `digitalocean/digitalocean` provider, App Platform App Spec YAML, DOKS GitOps with Argo CD / Flux, GitHub Actions with PATs, and image build via doctl registry. Use when starting a new IaC project, picking a tool, or hardening a release path.
---

# DigitalOcean Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — picking an IaC approach for DigitalOcean infrastructure.
- Bringing console-built resources into code.
- Designing a CI/CD pipeline for app and infrastructure changes.
- Hardening a release for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, secret leaks, or state hygiene.

## IaC tool selection

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu** (`digitalocean/digitalocean` >= 2.40) | Default choice. Manages all DigitalOcean resources: Droplets, DOKS, databases, Spaces, networking, DNS, firewalls. Largest community and module support. |
| **App Platform App Spec YAML** | Your entire workload runs on App Platform. Spec-driven; deployed with `doctl apps create` or `doctl apps update`. No state file to manage. |
| **doctl scripting** | Quick one-off operations, seed scripts, or where you need the CLI's full feature set (e.g., DOKS kubeconfig retrieval). Not suitable as a primary IaC tool — no drift detection, no state. |
| **Pulumi** (`pulumi-digitalocean` provider) | Team strongly prefers a general-purpose language (Python, TypeScript, Go) over HCL. Same coverage as Terraform but smaller community. |
| **Ansible** | Configuration management inside Droplets; complements Terraform for post-provisioning setup. Not a substitute for resource IaC. |

Mixed tools are acceptable with clean boundaries: Terraform for infrastructure (VPC, Droplets, databases, DOKS clusters), App Spec YAML for App Platform workloads, Ansible for in-guest configuration.

## Terraform state management

- **Remote backend:** S3-compatible backend pointing at a DigitalOcean Spaces bucket. Spaces supports the AWS S3 backend in Terraform with a few configuration overrides.

```hcl
terraform {
  backend "s3" {
    endpoint                    = "https://nyc3.digitaloceanspaces.com"
    region                      = "us-east-1"  # Required by S3 backend; not meaningful for DO
    bucket                      = "my-tf-state"
    key                         = "prod/terraform.tfstate"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

- **Locking:** Spaces does not support DynamoDB-style state locking. Use Terraform Cloud / HCP Terraform, or a small PostgreSQL-backed Atlantis instance, for locking if multiple operators need concurrent access.
- **Per-environment state:** separate state files per environment (`dev/terraform.tfstate`, `stage/terraform.tfstate`, `prod/terraform.tfstate`). Use Terraform workspaces or separate directories per environment — prefer directories for clarity.
- **Stateful resources:** databases, Spaces buckets, and Volumes should be in a separate Terraform root module from compute (Droplets, DOKS). This limits the blast radius of a compute change.
- **`prevent_destroy = true`:** on every stateful resource in prod. A `terraform destroy` without this guard can delete a production database in seconds.

## Provider configuration

```hcl
terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
  }
  required_version = ">= 1.6"
}

provider "digitalocean" {
  token = var.do_token  # Injected from environment; never hardcoded
}
```

- `do_token` should be set via `TF_VAR_do_token` from an environment variable or CI secret — never in `terraform.tfvars` checked into source control.
- The DigitalOcean provider supports Spaces access key authentication separately for `digitalocean_spaces_bucket` resources via `spaces_access_id` and `spaces_secret_key`. Keep these separate from the team PAT.

## App Platform App Spec YAML

The App Spec is the declarative description of an App Platform application. It is the preferred IaC for App Platform workloads.

```yaml
name: my-api
region: nyc
services:
  - name: api
    github:
      repo: myorg/myrepo
      branch: main
      deploy_on_push: false   # Drive deploys from CI, not auto-push
    build_command: go build -o server ./cmd/api
    run_command: ./server
    environment_slug: go
    instance_count: 2          # Min 2 for HA
    instance_size_slug: professional-xs
    http_port: 8080
    health_check:
      http_path: /healthz
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET           # Injected from App Platform encrypted env vars
        value: ""              # Set via doctl or Control Panel, not in the spec
```

- Never put secret values in the App Spec file. Use `type: SECRET` and set the value via `doctl apps update` or the Control Panel.
- `deploy_on_push: false` is the safe default for production — trigger deployments explicitly from CI after tests pass.
- Commit the App Spec to your repository and manage it as code. Apply changes with `doctl apps update <app-id> --spec app.yaml`.

## CI/CD pipeline

### Authentication for GitHub Actions

DigitalOcean does not support OIDC token exchange (as of 2026). GitHub Actions authenticate via a PAT stored as a GitHub Actions encrypted secret.

```yaml
- name: Install doctl
  uses: digitalocean/action-doctl@v2
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
```

- Use a dedicated CI PAT, separate from any human's personal token. Rotate on a 30-day schedule.
- Scope the CI PAT to the minimum required. Because DigitalOcean PATs have no fine-grained scope, use a dedicated team account for CI if blast-radius isolation is critical.

### Terraform plan/apply pipeline

```yaml
jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.8"
      - name: Terraform Init
        run: terraform init
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.SPACES_ACCESS_KEY }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.SPACES_SECRET_KEY }}
      - name: Terraform Plan
        run: terraform plan -out=tfplan
        env:
          TF_VAR_do_token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
      - name: Post Plan to PR
        uses: actions/github-script@v7
        # ... post plan output as PR comment

  apply:
    needs: [plan]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production   # Requires manual approval in GitHub
    # ...
```

- Post the plan output as a PR comment. Humans must review the plan before applying.
- Gate production applies on a GitHub Actions environment with a required reviewer.
- Never run `terraform apply` from a laptop in production. Pipeline-only applies with an audit trail.

### DOKS image build and push

```yaml
- name: Build and push container image
  run: |
    doctl registry login
    docker build -t registry.digitalocean.com/myregistry/myapp:${{ github.sha }} .
    docker push registry.digitalocean.com/myregistry/myapp:${{ github.sha }}

- name: Update DOKS deployment
  run: |
    doctl kubernetes cluster kubeconfig save ${{ env.CLUSTER_ID }}
    kubectl set image deployment/myapp myapp=registry.digitalocean.com/myregistry/myapp:${{ github.sha }}
    kubectl rollout status deployment/myapp --timeout=5m
```

- Tag images with the git SHA, not `:latest`.
- `kubectl rollout status` blocks until the rollout completes or times out — fail fast on deployment errors.
- Use `kubectl rollout undo deployment/myapp` for fast rollback; the previous ReplicaSet remains available.

## GitOps with Argo CD or Flux

For DOKS clusters, GitOps is the production-grade deployment pattern:

- **Argo CD:** install via Helm or the DOKS Marketplace add-on. Manage `Application` resources that point at your Kubernetes manifests or Helm chart repositories.
- **Flux:** lightweight alternative; install via Flux CLI. Manages `GitRepository`, `Kustomization`, and `HelmRelease` resources.
- **Image automation:** Argo CD Image Updater or Flux Image Automation Controller watches the Container Registry for new image tags matching a policy (semver, regex) and opens a PR or commits directly to the GitOps repo.
- **Secret management in GitOps:** never store Kubernetes secrets in the GitOps repository in plaintext. Use Sealed Secrets (`kubeseal`) or External Secrets Operator (pulling from HashiCorp Vault or AWS Secrets Manager) to manage secrets declaratively.

## Deployment patterns

| Pattern | How to implement on DigitalOcean |
| --- | --- |
| Rolling update | Default DOKS Deployment strategy; `kubectl rollout undo` for rollback. |
| Blue/green | Two DOKS Deployments; switch a Service selector; delete the old deployment after validation. |
| Canary | Argo Rollouts or Flagger with weighted traffic split via nginx ingress annotations. |
| App Platform rolling | App Platform performs rolling deploys by default with `min_instance_count` > 1. |
| Feature flags | LaunchDarkly, Statsig, or OpenFeature + a flag provider. DigitalOcean has no first-party feature flag service. |

Always define the rollback procedure before completing the forward deploy plan.

## Secrets in IaC

- The DigitalOcean PAT is the highest-privilege credential in your IaC setup. Treat it accordingly.
- Inject via environment variables (`TF_VAR_do_token`, `DIGITALOCEAN_ACCESS_TOKEN`); never commit it.
- App Platform secrets: set via `doctl apps update --spec` or the Control Panel API; stored encrypted in App Platform. The spec YAML should have `value: ""` as a placeholder.
- DOKS secrets: use External Secrets Operator pointing at HashiCorp Vault, AWS Secrets Manager, or any OIDC-compatible secrets backend. `kubectl create secret` from raw values in CI is acceptable only if the CI environment is fully isolated and the secret is rotated on each use.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| ClickOps with "we'll codify it later" | Drift accumulates; the "later" never comes. Codify before the second resource. |
| Terraform state in a local file | No remote access, no locking, gets committed to git by accident. Use Spaces backend. |
| `terraform apply` from a developer laptop in prod | No audit trail, no lock, mystery state, human error. Pipeline-only applies. |
| PAT in plaintext in `terraform.tfvars` | Committed to git; leaked in CI logs. Use environment variable injection. |
| `:latest` image tag in DOKS Deployment manifests | Rollback is impossible; image drift is silent. Use git SHA tags. |
| App Spec deployed manually via Control Panel | No audit trail, no PR review, configuration drift. Manage App Spec in source control. |
| No `prevent_destroy = true` on prod databases | One `terraform destroy` removes the production database. |
| Kubernetes secrets committed to GitOps repo in plaintext | Secrets visible to anyone with repo read access. Use Sealed Secrets or ESO. |

## Defaults — release pipeline

- Trunk-based development; feature branches are short-lived.
- PRs require: passing lint (`tflint`, `checkov` or `trivy` for IaC), a Terraform plan review, and at least one human reviewer.
- Container images tagged with git SHA; never `:latest` in any deployment manifest.
- Vulnerability scan on every image push to the Container Registry; CI fails on high/critical findings.
- Every deploy emits a structured event (annotation in Grafana, deployment marker in your APM tool) correlating code change to system behavior.
- Rollback is a single command: `kubectl rollout undo`, App Platform redeploy of a previous build, or a Terraform plan applying the previous state.

## Verification checklist

- [ ] IaC tool chosen with a documented reason; Terraform is the default unless App Spec fits.
- [ ] Terraform state in a Spaces backend; separate state per environment.
- [ ] `prevent_destroy = true` on all stateful resources (databases, Volumes, Spaces buckets holding state).
- [ ] No PAT or Spaces secret key in source control or `terraform.tfvars`.
- [ ] CI plan/apply pipeline with plan posted to PR and manual approval for prod.
- [ ] Image builds tagged with git SHA; vulnerability scanning gates prod deploys.
- [ ] GitOps pattern in place for DOKS; secrets managed via Sealed Secrets or ESO.
- [ ] App Spec YAML committed to source control; secrets are placeholders (`value: ""`).
- [ ] Rollback procedure tested at least once per quarter.
- [ ] Drift detection: scheduled `terraform plan -refresh-only` or Argo CD sync-status alerting.
