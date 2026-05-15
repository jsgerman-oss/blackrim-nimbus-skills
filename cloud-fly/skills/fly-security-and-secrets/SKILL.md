---
name: fly-security-and-secrets
description: Design or audit Fly.io security posture — Fly tokens (org/app/deploy scope), fly secrets management, SSO and org membership, private apps via Flycast, least-privilege token handling, secret rotation, image hardening. Use when scoping credentials, rotating secrets, designing a private app, or reviewing the security posture of a Fly-hosted service.
---

# Fly Security and Secrets

## When to use

- Setting up token scopes for CI/CD pipelines.
- Injecting application secrets and rotating them without downtime.
- Hardening an app to be accessible only within the 6PN private network.
- Reviewing org membership and access for departing team members.
- Designing an SSO-enforced Fly organization.
- Auditing which apps have public IPs vs private-only access.

## Authentication — Fly tokens

Fly has two authentication surfaces: the user-facing `fly auth` OAuth flow and machine-to-machine tokens.

### Token types

| Type | Scope | Create with | Typical use |
| --- | --- | --- | --- |
| **Org token** | Full org access — all apps, all ops | `fly tokens create org` | Admin automation; avoid in CI |
| **App token** | One app, read/write | `fly tokens create deploy -a <app>` | CI deployment for one app |
| **Deploy token** | One app, deploy-only (no secret read) | `fly tokens create deploy -a <app> --expiry 24h` | Narrowest for GitHub Actions |
| **Personal access token** | Your user scope | Fly dashboard → "Access Tokens" | Developer tooling, local scripts |

**Default for CI: use deploy tokens, not org tokens.** A deploy token cannot read secrets, cannot delete apps, and cannot access other apps in the org. Scope to the minimum required action.

**Token expiry:** always set `--expiry`. Indefinite tokens are a compromise waiting to happen. For GitHub Actions, regenerate monthly or tie to repo-level rotation schedule.

### `fly auth` and SSO

For human users, `fly auth login` completes an OAuth flow. For organizations with SSO requirements, Fly supports Google Workspace and GitHub OAuth — enforce via the org dashboard under "Authentication". SSO enforcement means no member can log in with email/password; all access goes through the IdP.

Departing team members: remove from the Fly org immediately (`fly orgs members remove`). Their personal tokens become invalid within minutes of removal. Audit membership quarterly (`fly orgs members list`).

## Secrets — `fly secrets`

Fly Secrets are the canonical way to inject sensitive values into Fly Machines at runtime. They are:

- **Encrypted at rest** in Fly's secrets store.
- **Injected as environment variables** into every Machine of the app at boot.
- **Never stored in `fly.toml`** — that file is version-controlled and plaintext.
- **Not readable after creation** — `fly secrets list` shows key names only, not values. To inspect a secret value, you must know it before setting.

### Setting and rotating secrets

```bash
# Set a secret (triggers rolling deploy by default)
fly secrets set DATABASE_URL="postgres://app:secret@mydb.internal:5432/appdb" -a myapp

# Set multiple secrets at once
fly secrets set \
  DATABASE_URL="postgres://..." \
  REDIS_URL="redis://..." \
  SIGNING_KEY="$(openssl rand -hex 32)" \
  -a myapp

# Rotate a secret with minimal downtime
# 1. Update the secret
fly secrets set SIGNING_KEY="$(openssl rand -hex 32)" -a myapp
# 2. Fly triggers a rolling deploy; old machines drain before the new key is active
# 3. If your app reads secrets at boot, new machines pick up the new value

# Remove a secret
fly secrets unset OLD_SECRET -a myapp
```

### What belongs in `fly secrets`

- Database connection strings (Postgres, Redis URLs with credentials).
- API keys for third-party services (Stripe, SendGrid, etc.).
- JWT signing keys, cookie secrets.
- S3 / Tigris credentials (if not automatically injected by Fly storage attachment).
- Any value that would cause a security incident if committed to source control.

### What does not belong in `fly secrets`

- Non-sensitive configuration that varies by environment (use `fly.toml` `[env]` for this).
- Large blobs (files, certificates for passthrough TLS) — mount via volume instead.
- Secrets needed at build time — Fly Secrets are runtime only. Build-time secrets must use Docker BuildKit `--secret` (never `ENV` or `ARG` in the final image layer).

### Secrets-free images

**Never bake secrets into a Docker image.** Even intermediate layers (`RUN apt-get install --token=...`) are reachable via `docker history`. Use Docker BuildKit `--secret` mount for build-time credentials:

```dockerfile
# GOOD — build secret not captured in image layer
RUN --mount=type=secret,id=github_token \
    GITHUB_TOKEN=$(cat /run/secrets/github_token) go build ./...

# BAD — token committed to image history
ARG GITHUB_TOKEN
RUN GITHUB_TOKEN=$GITHUB_TOKEN go build ./...
```

## Private apps — reducing public exposure

An app with no `[[services]]` block and no public IP is accessible only via 6PN and Flycast. This is the correct posture for any internal service (database proxy, admin panel, background worker API).

### Making a service private

```toml
# fly.toml — remove the [[services]] block entirely
# (and remove any public IPs allocated with fly ips)
```

Then route internal consumers to it via 6PN DNS: `http://myservice.internal:8080`.

For load-balanced access to a private multi-machine app, use Flycast (see `fly-networking-and-edge`).

### `auto_stop_machines` and private apps

Scale-to-zero works for private apps too. Internal callers that hit the 6PN address will trigger auto-start. This is safe as long as:

1. The internal caller handles cold-start latency.
2. The Machine's health check reflects real readiness.

## Least-privilege org membership

- **Owner** — full org control. Limit to one or two named individuals.
- **Member** — can deploy to apps they are granted access to. Default for developers.
- **Billing** — read-only billing view. For finance access without app access.

Do not grant Owner access to CI pipelines. Use deploy tokens. Do not share personal access tokens among developers.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Org token in GitHub Actions secrets | Any PR author can read it via `echo $FLY_API_TOKEN`. Use a deploy token scoped to one app. |
| Indefinite token expiry | Forgotten token from a departed developer retains org access. Set `--expiry` on every machine token. |
| Secrets in `fly.toml [env]` | `fly.toml` is committed to source control; plaintext values visible to anyone with repo access. |
| `ENV DATABASE_URL=...` in Dockerfile | Baked into every image layer; leaked in any registry with public pull access. |
| Database on a public `[[services]]` port | Postgres or Redis on a public anycast IP with only a password for protection. |
| Shared developer WireGuard peer | One developer's compromised machine = org-wide 6PN access. One peer per developer. |
| No secret rotation schedule | Credentials from an old engineer remain valid indefinitely. Rotate on personnel changes and on a calendar schedule. |

## Security defaults

- Every CI deployment uses a deploy token, not an org token or personal token.
- Tokens have expiry: 30 days for CI tokens, shorter for ephemeral build environments.
- All internal services: no public `[[services]]`, no dedicated IP. 6PN or Flycast only.
- `fly secrets` for all credentials. Zero credentials in `fly.toml`, Dockerfile, or source code.
- Postgres connection string uses a least-privilege app user, not the superuser.
- Image built without secrets in layers. Verified with `docker history --no-trunc`.
- WireGuard peers: one per developer; rotate quarterly and on offboarding.
- Org SSO enforced where Fly supports it (Google Workspace or GitHub org).

## Observability defaults

- Audit `fly tokens list` and `fly orgs members list` quarterly.
- Fly does not currently provide a native audit log for secret access — ship application-level access logs to an external SIEM to bridge this gap.
- Alert on: unexpected machine restarts (may indicate secret injection failure), 401 / 403 responses from internal services (may indicate token or credential expiry).

## Cost considerations

- Secrets, tokens, and org membership controls have no direct cost.
- Security investment is dominated by engineering time: token rotation procedures, secret management workflows, and incident response playbooks.
- The cost of a credential breach (data loss, regulatory fine, customer churn) vastly exceeds the cost of rotating tokens monthly.

## IaC hints

- `fly secrets` is imperative by design — secrets are not version-controlled by Fly. Document the set of required secrets in a `secrets.example.env` file (no values, only keys and a description for each).
- Bootstrap scripts (`scripts/bootstrap-secrets.sh`) can read from a password manager (1Password CLI, Vault) and push to Fly secrets on first deploy.
- Pulumi and Terraform do not manage `fly secrets` natively — use the `fly` CLI in provisioning scripts or a tool like `doppler` for centralized secrets management.
- For GitOps environments, consider pushing secrets as part of a deploy workflow with least-privilege deploy tokens.

## Verification checklist

- [ ] CI uses a deploy token (not org or personal token); expiry set.
- [ ] Zero credentials in `fly.toml`, Dockerfile, or any file tracked by git.
- [ ] `fly secrets list` shows all expected keys for each app; no extra leftover keys.
- [ ] Internal services have no public `[[services]]` block and no dedicated IP.
- [ ] Postgres connection string uses a non-superuser app user.
- [ ] Docker image history shows no secret values in layers.
- [ ] WireGuard peer list matches current team; stale peers removed.
- [ ] Org member list reviewed; no former team members with active access.
- [ ] Secret rotation schedule documented and calendared.
