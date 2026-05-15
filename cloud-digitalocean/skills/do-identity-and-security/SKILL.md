---
name: do-identity-and-security
description: Design or audit DigitalOcean identity and security posture — Teams (members, roles), Personal Access Tokens (PATs — scopes, rotation), OAuth applications, doctl authentication, Container Registry vulnerability scanning, Cloud Firewall posture, agent monitoring vs metrics agent, and project-based isolation. Use when writing access policies, rotating secrets, scoping tokens, or hardening a team account.
---

# DigitalOcean Identity and Security

## When to use

- Setting up a new team or inviting members with appropriate roles.
- Scoping and rotating Personal Access Tokens for CI/CD or application use.
- Configuring OAuth applications for delegated DigitalOcean API access.
- Reviewing a team's MFA enforcement posture.
- Auditing Cloud Firewall rules for over-exposure.
- Configuring Container Registry vulnerability scanning.
- Isolating resources by project for access control and billing separation.

## Identity model

DigitalOcean's identity model is simpler than hyperscaler IAM but has distinct rules that require deliberate design:

- **Humans → Team Members with Roles.** Invite individuals by email. Available roles: Owner (full control including billing), Billing (billing page only), and Member (everything except billing and team management). There is no fine-grained per-resource role policy — all Members see and can manage all resources in the team.
- **Workloads → Personal Access Tokens (PATs) or OAuth Apps.** CI/CD pipelines, Terraform, and `doctl` authenticate via a PAT or an OAuth app's client credentials. There are no workload-identity primitives (no role assumption, no short-lived OIDC tokens from DigitalOcean itself) — the token is the credential.
- **External CI (GitHub Actions, GitLab) → PAT stored as CI secret.** There is no OIDC federation to DigitalOcean as of 2026; a PAT is the only machine credential. This makes PAT hygiene (scope, rotation, expiry) critical.
- **doctl:** authenticates via `doctl auth init` with a PAT. The PAT is stored in `~/.config/doctl/config.yaml`. Audit what is stored there in shared environments.

## Personal Access Tokens — the hardest problem

PATs are the primary attack surface for DigitalOcean accounts. A leaked PAT with full scope can delete every resource in the team.

- **Scope:** as of 2026, DigitalOcean PATs are all-or-nothing — a single PAT has full API access to the entire team. There are no fine-grained API scopes per token. Design around this: use separate team accounts for environments where blast-radius separation matters, not separate PATs.
- **Expiry:** set an expiry date on every PAT. DigitalOcean supports token expiry; use it. Never create a non-expiring PAT for a CI pipeline.
- **Rotation:** rotate PATs on a schedule (90-day maximum; 30-day for CI pipelines with high exposure). Treat rotation as a fire drill — it should take minutes, not hours.
- **Storage:** store PATs in a secrets manager (HashiCorp Vault, AWS Secrets Manager, GitHub Actions encrypted secrets). Never commit a PAT to source control or log it to a CI console.
- **Audit:** DigitalOcean does not provide a per-token last-used audit log as of 2026. Treat every active PAT as potentially in use; the only way to know a PAT is unused is to delete it and observe.
- **Least-privilege architecture:** since PATs carry full scope, separation of access requires separate DigitalOcean team accounts. A typical pattern: one team account per environment (dev, stage, prod), with separate billing and separate PATs. This is operationally heavier but provides real blast-radius isolation.

## OAuth Applications

- OAuth apps are appropriate for third-party integrations that need to act on behalf of a user or team.
- The callback URL must be explicitly registered; reject any OAuth app with a wildcard or HTTP callback.
- OAuth apps have read/write scopes over the DigitalOcean API; treat a compromised OAuth app client secret as equivalent to a leaked PAT.
- Revoke OAuth app tokens when the integration is decommissioned. DigitalOcean does not auto-expire OAuth grants.

## MFA enforcement

- Every team member MUST have MFA enabled, especially Owner-role accounts. A phished Owner credential with no MFA = full team compromise.
- DigitalOcean supports TOTP (authenticator app) and SMS. Require TOTP — SMS is vulnerable to SIM-swap attacks.
- As of 2026, DigitalOcean does not enforce MFA at the team policy level — you cannot block login for MFA-less users via a policy. Enforce via process and periodic audit: `doctl teams members list` does not expose MFA status directly; use the Control Panel audit.
- Include MFA status in quarterly access reviews.

## Container Registry vulnerability scanning

- Enable vulnerability scanning on every repository push via the DigitalOcean Container Registry dashboard.
- Review scan results before deploying an image to production. Block high and critical findings in your CI pipeline using `doctl registry repository list-manifests` and checking the digest's vulnerability status.
- DOKS pulls from the Container Registry using a registry integration — enable this integration so DOKS nodes authenticate automatically without storing a registry PAT in a Kubernetes secret.
- Delete old image tags on a schedule; old unscanned images accumulate vulnerabilities silently.
- Use image digest references (`image@sha256:...`) in production Kubernetes manifests rather than mutable tags.

## Project-based isolation

DigitalOcean Projects provide resource grouping and basic access boundaries:

- Assign every resource (Droplet, database, Spaces bucket, domain, Load Balancer, DOKS cluster) to a project. Unassigned resources are in the "Default" project and invisible to project-scoped operators.
- Projects enable cost reporting per project — this is the primary cost isolation primitive in DigitalOcean.
- Projects do not enforce access control at the resource level (any team Member can see all projects). They are an organizational and billing tool, not a security boundary.
- For environment separation with a real security boundary, use separate DigitalOcean team accounts.

## doctl authentication

- `doctl auth init` stores the PAT in plaintext in `~/.config/doctl/config.yaml` by default. On shared machines or CI runners, use `DIGITALOCEAN_ACCESS_TOKEN` environment variable injection from a secrets manager instead.
- Multiple contexts: `doctl auth switch --context <name>` allows switching between PATs for different team accounts. Use named contexts to avoid operating on the wrong environment.

## Cloud Firewall posture

- Cloud Firewall is your primary network security control for Droplets. See `do-networking-and-edge` for rule design; this section focuses on posture review.
- Audit all firewalls quarterly with `doctl compute firewall list` and verify that every inbound rule has a documented justification.
- No firewall rule should allow inbound `0.0.0.0/0` on any port except 80 and 443 on explicitly public-facing load balancers.
- Rules that allow `0.0.0.0/0` on management ports (22, 3389, 5432, 6379, 27017) are critical findings — remediate immediately.
- Tag-based firewall assignment: verify that all production Droplets have the correct tags applied and therefore the correct firewall. A Droplet without the production tag may have no firewall.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Non-expiring PAT for CI/CD | Leaks a persistent credential with full team access; no rotation cycle. |
| PAT hard-coded in a Dockerfile, `.env`, or repository | Git history is permanent; rotate immediately, scan with `gitleaks` or `trufflehog`. |
| All environments in one DigitalOcean team account | A dev-account compromise or accidental `doctl compute droplet delete` affects prod. |
| Owner-role accounts without TOTP MFA | Single credential compromise = full team takeover, including billing. |
| Container images deployed from tags, not digests | Tag is mutable; digest is immutable. A tag-based deploy can silently switch the image. |
| OAuth app client secret stored in a shared password manager | No rotation audit trail; anyone with vault access can impersonate the app. |
| Resources left in the Default project | No cost attribution, invisible to project-scoped reporting. |

## Security defaults

- Enforce TOTP MFA on all team members, especially Owners. Conduct a quarterly MFA audit.
- All PATs have an expiry date; no non-expiring tokens exist in CI or production systems.
- PATs stored in a secrets manager and referenced by environment variable; never hard-coded.
- Container Registry vulnerability scanning enabled; CI pipeline gates on scan results for high and critical findings.
- Cloud Firewall applied to every Droplet; rules use tags; no `0.0.0.0/0` on management ports.
- All resources assigned to a project; "Default" project is empty.
- Separate DigitalOcean team accounts for production and non-production if budget and operations allow.

## Observability defaults

- Audit team membership quarterly: `doctl teams members list`. Remove former employees and contractors immediately upon offboarding.
- Audit active PATs at each rotation cycle. Delete any PAT that cannot be attributed to a specific service or person.
- Monitor the DigitalOcean audit log (available in the Control Panel under Settings > Security) for Owner-level actions: resource deletions, billing changes, team member additions.
- Alert on Container Registry scan results that introduce new high/critical vulnerabilities. Wire this into your CI failure notifications.

## Cost considerations

- MFA, PATs, and team management are free.
- Container Registry vulnerability scanning is included with the Container Registry service. Container Registry costs are based on storage: $5 / month for the Starter plan (5 GB), custom pricing for Pro.
- Separate team accounts for environment isolation incur separate billing and overhead — weigh operational cost against the security benefit. For most teams, a single account with disciplined PAT and project management is an acceptable tradeoff until a compliance requirement forces separation.

## IaC hints

- Terraform does not manage DigitalOcean team members or PATs — these are human-controlled. Document team membership and PAT lifecycle in runbooks, not in IaC.
- Terraform resource `digitalocean_project` and `digitalocean_project_resources` manage project membership. Include every resource in a project assignment block.
- Container Registry: `digitalocean_container_registry` and `digitalocean_container_registry_docker_credentials` (used to push from CI). The docker credentials resource generates a short-lived credential — prefer it over storing a long-lived PAT as a registry password.
- Cloud Firewall: `digitalocean_firewall` resource with `inbound_rule` blocks sourcing from `tags`. Never use `source_addresses = ["0.0.0.0/0", "::/0"]` on database or management ports.

## Verification checklist

- [ ] All team members have TOTP MFA enabled.
- [ ] No Owner-role accounts without hardware or TOTP second factor.
- [ ] All PATs have an expiry date set; no non-expiring tokens in CI.
- [ ] PATs stored in a secrets manager; none committed to source control.
- [ ] Container Registry vulnerability scanning enabled on all repositories.
- [ ] CI pipeline gates on registry scan results for high/critical findings.
- [ ] Cloud Firewall applied to all production Droplets via tags.
- [ ] No `0.0.0.0/0` inbound on any port except 80/443 for public LBs.
- [ ] All resources assigned to a project; Default project is empty.
- [ ] Quarterly access review scheduled: team members, PATs, OAuth apps.
