---
name: cf-zero-trust-and-security
description: Design or audit Cloudflare Zero Trust and security posture — Access (ZTNA / identity-aware proxy), Gateway (SWG / DNS filtering), WAF, Bot Management, DDoS posture, Page Shield, Magic Firewall, API Shield. Use when securing an application, filtering egress, building a Zero Trust network, or reviewing WAF coverage.
---

# Cloudflare Zero Trust and Security

## When to use

- Putting identity-aware access control in front of an internal application or SSH/RDP target.
- Filtering DNS and HTTP egress from managed devices via Gateway.
- Reviewing or writing WAF custom rules; enabling managed rulesets.
- Enabling Bot Management for a public site that experiences credential stuffing, scraping, or fraud.
- Auditing DDoS posture or enabling Magic Firewall for network-layer filtering.
- Enabling Page Shield to detect malicious scripts loaded by your frontend.
- Securing an API surface with API Shield (schema validation, mutual TLS, sequence mitigation).

## Cloudflare Access (ZTNA)

Access is an identity-aware reverse proxy. It terminates TLS, verifies the caller's identity (via an identity provider), evaluates policy, then forwards to the origin or Tunnel.

### Defaults

- **Applications**: create one Access Application per protected resource. Types: Self-hosted (HTTP/HTTPS via Tunnel or public hostname), SSH, RDP, Infrastructure (SSH/RDP with browser rendering), SaaS (SAML/OIDC for SaaS apps).
- **Identity providers**: connect at least one corporate IdP (Okta, Entra ID, Google Workspace, JumpCloud). Use SAML or OIDC. Cloudflare's built-in one-time PIN (email OTP) is a fallback only — do not use it as the primary IdP for sensitive applications.
- **Policies**: Access policies are evaluated top-down with Allow / Block / Bypass actions. Default-deny: unless a rule explicitly allows, access is denied.
  - `Include`: who can attempt access.
  - `Require`: additional conditions that must all pass (e.g., `Device Posture: disk encryption = on`).
  - `Exclude`: always deny regardless of includes.
- **Device posture checks**: require corporate device certificates, disk encryption, OS version minimum, or endpoint detection and response (EDR) agent enrollment. Combine with `Require` in the policy.
- **Service tokens**: machine-to-machine access uses Access Service Tokens (client ID + secret) — never a user's identity token. Rotate service tokens on a schedule.
- **Short-lived certificates**: for SSH targets, issue short-lived certs (Access for Infrastructure) instead of distributing long-lived SSH keys.
- **Audience tags**: every Access Application has an AUD tag; validate it in Workers or origin apps to prevent access token replay from other applications.

## Gateway (Secure Web Gateway)

Gateway filters DNS and HTTP traffic from managed devices enrolled in the Cloudflare WARP client or configured proxy.

### Defaults

- **DNS filtering**: create DNS policies to block categories (malware, phishing, cryptomining) and specific FQDNs. Log all queries to Logpush for forensic visibility.
- **HTTP filtering**: inspect HTTP traffic for malware, DLP patterns (credit card numbers, SSNs), and policy violations. Requires WARP client with TLS inspection enabled.
- **TLS inspection**: Gateway issues a locally-trusted certificate to inspect HTTPS traffic. Configure a certificate trust policy for managed devices (push the Cloudflare root cert via MDM).
- **Do Not Inspect list**: exclude applications that break under TLS inspection (banking apps, certificate-pinned apps) — but minimize the exclusion list; every exclusion is a blind spot.
- **Egress policies**: restrict which SaaS applications users can access; log or block uploads to personal cloud storage.
- **Resolver policies**: split-horizon DNS for internal domains — route internal FQDNs via Gateway to internal resolvers, public FQDNs via Cloudflare's 1.1.1.1 for speed and security.

## WAF (Web Application Firewall)

### Defaults

- **Managed rulesets**: enable Cloudflare's managed ruleset (OWASP-based) in **Log** mode first, then **Block** after reviewing the log for false positives. Cloudflare Free Threat Intelligence (CFTINTELLIGENCE) ruleset is automatic on Pro and above.
  - Core ruleset: SQL injection, XSS, file inclusion, path traversal.
  - Known bad inputs: attack signatures maintained by Cloudflare Threat Intelligence.
  - Anonymous IP list: block or challenge Tor exit nodes, hosting providers, VPNs where appropriate.
- **Custom rules**: write custom WAF rules using Cloudflare's Rules language (`http.request.uri.path`, `http.request.headers["x-api-key"]`, etc.). Use `skip` action with `managed_challenge` or `block` based on the threat level.
- **Rate limiting**: rate-limit rules at the zone level (not just WAF — Rate Limiting is its own ruleset category). Apply to every public API endpoint and login route. Use `challenges` (managed challenge or JS challenge) before `block` to avoid blocking legitimate users behind CGNATs.
- **Exposed credential check**: Cloudflare's WAF can compare submitted credentials against breach databases and challenge or block matching requests — enable on login and account creation endpoints.
- **Log-to-block discipline**: always deploy new rules in `log` mode first. Review rule hits in Security Events before switching to `block`. A rule that blocks on day one without traffic review will eventually block legitimate users.

## Bot Management

Bot Management classifies requests by bot score (0–100; higher = more likely human) and provides signals for taking action.

### Defaults

- **Bot Fight Mode** (Free/Pro): basic bot blocking, limited customization — a starting point.
- **Super Bot Fight Mode** (Pro/Business): more signals, custom rules based on bot score thresholds.
- **Bot Management** (Enterprise): full control — bot score in Rules language, JavaScript detections, machine learning model scores, verified bot allowlist.
- Allow verified good bots: search engine crawlers, monitoring bots, uptime checkers. Use the `cf.bot_management.verified_bot` field to allow them explicitly.
- Challenge bots rather than blocking when uncertain — managed challenges are nearly invisible to real users.
- Combine Bot Management with WAF rate-limiting for layered defence against credential stuffing.
- Page Shield relies on Bot Management signals to identify scraping and data exfil patterns.

## DDoS Posture

- Cloudflare DDoS protection is **automatically applied** to all proxied zones — no explicit configuration needed for HTTP DDoS.
- **Network-layer DDoS**: Magic Transit for infrastructure IP protection (enterprise).
- **Application-layer tuning**: the DDoS ruleset can be customized in `Security > DDoS`. Override sensitivity or action for specific paths (e.g., lower the sensitivity threshold for API endpoints that handle high-volume automation legitimately).
- **Under-attack mode**: available manually in the dashboard or via API. Issues a browser-integrity challenge to every visitor. Use only during an active attack — it blocks many legitimate users.
- Never disable DDoS protection for an extended period — even for testing. Use a low-sensitivity override for test traffic instead.

## Page Shield

Page Shield monitors scripts loaded by your frontend for malicious modifications (supply chain attacks, Magecart-style skimmers).

### Defaults

- Enable in `Security > Page Shield`. Free monitoring available; policy enforcement (blocking unapproved scripts) on Business and Enterprise.
- Review the detected scripts list; approve known-good scripts. Unapproved scripts trigger alerts or blocks in enforce mode.
- Integrate Page Shield alerts with your security notification channel (PagerDuty, Slack via webhook).
- Combine with a strict `Content-Security-Policy` header to reduce the attack surface Page Shield needs to monitor.

## Magic Firewall

Magic Firewall applies packet-level (OSI Layer 3/4) filtering for Magic Transit and Magic WAN traffic.

- Write rules using Wireshark-style packet filter syntax or the Rules language.
- Use to block IP ranges, protocols, or port ranges at the Cloudflare network edge — before traffic reaches your infrastructure.
- Covered here at an overview level; requires Magic Transit or Magic WAN (enterprise).

## API Shield

API Shield protects APIs with schema validation, mTLS, and sequence enforcement.

### Defaults

- **Schema validation**: upload an OpenAPI schema; Cloudflare enforces it at the edge, blocking requests that don't match (unknown fields, wrong types, extra paths).
- **Mutual TLS (mTLS)**: require client certificates for machine-to-machine API traffic. Cloudflare validates the cert; the origin trusts Cloudflare. Upload the CA cert to Cloudflare and create a mTLS Access rule.
- **Sequence mitigation**: detect and block API calls made out of expected sequence (e.g., a client that skips the auth step and calls `/api/resource` directly).
- **API Discovery**: Cloudflare automatically inventories detected API endpoints — review to find undocumented or shadow APIs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Access with one-time PIN as the only IdP | OTP to email is phishable. Corporate IdP + device posture is required for sensitive resources. |
| WAF rules deployed in Block mode without log review | Rules with false positives block real users before you find out. Always Log → review → Block. |
| Disabling TLS inspection for an entire domain "because it might break" | Entire category of HTTPS exfil and malware goes undetected. Exclude specific apps, not entire domains. |
| Service tokens that never rotate | Long-lived tokens that leak remain valid until manually revoked. Rotation schedule required. |
| Bot Management blocking all non-human traffic | Verified bots (search engines, monitoring) must be explicitly allowed or your SEO and uptime checks break. |
| Under-attack mode left on permanently | It blocks significant fractions of legitimate users. Use only during active attacks; disable after. |
| No rate limiting on login or password-reset routes | Credential stuffing and brute force attacks run unimpeded. |
| API Shield schema validation in log mode, never enforced | Shadow endpoints and malformed requests continue undetected. Move to block after baseline. |

## Security defaults

- Access: corporate IdP + device posture check on all internal applications; no one-time PIN as primary.
- WAF: managed rulesets enabled; exposed credential check on login endpoints; rate limiting on all public API routes.
- Bot Management: verified bots explicitly allowed; managed challenge applied to bot score < 30 for user-facing pages.
- Gateway: DNS policy blocks malware, phishing, cryptomining categories; TLS inspection on with minimal exclusion list.
- DNSSEC and CAA on every zone (see `cf-networking-and-edge`).
- Page Shield: enabled with alerts on script change detection.
- API Shield: mTLS for B2B/machine APIs; OpenAPI schema validation enforced.
- API tokens (for Cloudflare control plane): scoped per zone/account resource, per permission (never global); rotated on access revocation.

## Observability defaults

- Security Events (WAF dashboard): review daily for unexpected blocks or high-volume challenges.
- Access audit logs: Logpush to R2 or SIEM — every Access policy decision logged with identity, device posture result, and action.
- Gateway DNS/HTTP logs: Logpush to R2 or SIEM — full query and response visibility.
- Bot Management: track bot score distribution and challenged/blocked request counts over time.
- Page Shield: alert on new unrecognized script detection.
- Cloudflare Notifications: configure alert policies for WAF attack volume, DDoS event, and bot traffic spikes.

## Cost considerations

- Access: included in Zero Trust plans; pricing per seat (user who authenticates at least once per month). Service token authentications do not count as seats.
- Gateway: included in Zero Trust plans; DNS filtering free, HTTP filtering requires paid plan for TLS inspection.
- WAF: managed rulesets included in Pro and above; custom rules billed per active rule on some plans — verify against your plan.
- Bot Management: Super Bot Fight Mode on Pro; full Bot Management on Enterprise. Bot Fight Mode (Free/Pro) is basic.
- Page Shield: basic monitoring free; policy enforcement Business/Enterprise.
- API Shield: Business and Enterprise.
- Magic Firewall / Magic Transit / Magic WAN: enterprise contract pricing.

## IaC hints

- Terraform `cloudflare/cloudflare` ≥ 5.x: `cloudflare_zero_trust_access_application`, `cloudflare_zero_trust_access_policy`, `cloudflare_zero_trust_gateway_policy`, `cloudflare_ruleset` (for WAF custom rules and managed ruleset configuration), `cloudflare_bot_management`.
- Access Service Tokens: `cloudflare_zero_trust_access_service_token` — store the client secret in your secrets manager, not in Terraform state.
- WAF managed ruleset overrides: `cloudflare_ruleset` resource with `kind = "zone"` and `phase = "http_request_firewall_managed"`.

## Verification checklist

- [ ] All internal applications protected by Access with corporate IdP + device posture.
- [ ] Access Service Tokens rotated on a defined schedule; no long-lived tokens.
- [ ] WAF managed rulesets enabled; exposed credential check on login routes.
- [ ] Rate limiting on all public API and auth endpoints.
- [ ] WAF rules in Block mode only after log-review period.
- [ ] Bot Management verified-bot allowlist present; non-human traffic challenged appropriately.
- [ ] Gateway DNS policy blocks malware/phishing; TLS inspection active on managed devices.
- [ ] Page Shield monitoring active; alerts wired to notification channel.
- [ ] API Shield schema validation enforced (not log-only) for production APIs.
- [ ] All Cloudflare API tokens scoped to minimum permissions; no global tokens in use.
- [ ] Logpush configured for Access, Gateway, and WAF events to R2 or SIEM.
