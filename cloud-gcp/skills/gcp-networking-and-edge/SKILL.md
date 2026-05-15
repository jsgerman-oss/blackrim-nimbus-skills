---
name: gcp-networking-and-edge
description: Design or audit GCP networking — VPC (auto vs custom, Shared VPC), Cloud Load Balancing (Global vs Regional, Application / Network), Cloud CDN, Cloud Armor, Cloud DNS, VPC Service Controls, Private Service Connect, Cloud NAT. Use when standing up a new VPC, exposing a service, hardening edge, or auditing connectivity.
---

# GCP Networking and Edge

## When to use

- Designing a new VPC for a project or workload.
- Exposing an internal service to the internet or to another VPC.
- Tuning latency, TLS, or WAF and DDoS posture at the edge.
- Auditing north-south and east-west connectivity (VPC peering, Shared VPC, Private Service Connect, VPN, Interconnect).
- Diagnosing NAT egress costs or unexpected cross-region traffic.

## VPC design — the production baseline

- **Custom-mode VPC** for all production projects. Auto-mode VPCs create a subnet in every region with overlapping CIDRs — impractical for peering and Shared VPC. Convert or recreate before you regret it.
- CIDR: allocate generous, non-overlapping RFC-1918 ranges from the start. `/16` per VPC; `/20` or `/22` subnets give enough room for growth. Plan the overall range allocation centrally if you use Shared VPC.
- Subnets per region (spread across zones at the workload layer, not the subnet layer — GCP subnets are regional, not zonal):
  - `private-workloads` — application compute (Cloud Run via VPC connector, GKE nodes, Cloud SQL).
  - `proxy-only` — required for regional Application Load Balancers (Envoy-based); dedicated subnet, `/24` minimum.
  - `ilb-only` — for Internal Load Balancers if you need a separate range.
- Private Google Access: enabled on every private subnet so VMs and GKE nodes reach GCP APIs without going to the internet.
- VPC Flow Logs: enabled on every subnet used for production. `INCLUDE_ALL_METADATA` for forensics; `EXCLUDE_INTERNAL_TRAFFIC` is acceptable for cost reduction on high-volume meshes.

## Shared VPC

- Use Shared VPC when multiple projects need connectivity to each other's resources without VPC peering meshes.
- The host project owns the subnets; service projects attach and use them.
- IAM binding: service project service accounts get `roles/compute.networkUser` on the shared subnet — not on the host project.
- One Shared VPC per environment (dev, stage, prod) in the same folder. Do not share a production VPC with a development project.

## Cloud NAT

- Regional NAT for outbound internet egress from private instances (GKE nodes, Compute Engine without external IP, Cloud Run with VPC connector / Direct VPC Egress).
- NAT IP allocation: automatic (Google-managed) for most workloads; manual static IPs only if the destination requires IP allowlisting.
- Endpoint-independent mapping: enable for workloads that maintain UDP sessions or use WebSockets.
- Logging: enable `ERRORS_ONLY` at minimum; `ALL` for NAT-level traffic forensics (verbose, costs money).
- One Cloud NAT per VPC per region — Cloud NAT is not zonal.

## Load balancing

| Use case | Pick |
| --- | --- |
| Global HTTPS service, HTTP(S) routing, Google's edge PoPs | Global Application Load Balancer |
| Regional HTTPS service, lower latency within a region | Regional Application Load Balancer |
| TCP/UDP passthrough, preserve client IP, extreme throughput | Regional external passthrough Network Load Balancer |
| Internal HTTP(S) between services inside a VPC | Regional internal Application Load Balancer |
| Internal TCP/UDP between services inside a VPC | Regional internal passthrough Network Load Balancer |
| TLS termination at scale with SNI routing | Global Application Load Balancer with SSL certificates |

Global Application Load Balancer defaults: HTTPS-only (HTTP → HTTPS redirect rule); modern SSL policy (`MODERN` or custom with TLS 1.2 minimum); Google-managed SSL certificates where possible; backend bucket (Cloud Storage) or backend service (NEG / instance group); enable Cloud CDN and Cloud Armor on every public-facing backend.

## Cloud CDN

- Attach to any Global Application Load Balancer backend that serves cacheable content.
- Cache mode: `CACHE_ALL_STATIC` is the safe default; `USE_ORIGIN_HEADERS` when the origin sets `Cache-Control` correctly; `FORCE_CACHE_ALL` only when you fully control TTL and understand purge workflows.
- Signed URLs / Signed Cookies: for protected content that should not be publicly cacheable without a token.
- Cache invalidation: available but slow (propagates in minutes). Prefer versioned URLs (`/assets/app-v2.js`) over cache invalidation as the deployment pattern.

## Cloud Armor

- Security policy attached to every external-facing Application Load Balancer backend service.
- Pre-configured WAF rules: enable the OWASP Top 10 rule set (`evaluatePreconfiguredWaf('sqli-v33-stable', ...)`, `xss-v33-stable`, `lfi-v33-stable`, `rce-v33-stable`, `rfi-v33-stable`, `methodenforcement-v33-stable`). Start in preview mode (`action = "allow", preview = true`) to observe before enforcing.
- Adaptive Protection: enable for automatic DDoS signal analysis; it surfaces anomalies and generates suggested rules.
- Rate-based bans: a catch-all rate limit rule is mandatory on every public origin. Start at 100 requests per minute per IP as a baseline; tune from real traffic data.
- Geo-based policies: allowlist or blocklist countries only when there is a clear business or compliance reason — not as a primary security control.
- Named IP lists: use managed threat intelligence lists (`threatintelligence.iplist-*`) for known scanner and malicious bot ranges.

## Cloud DNS

- Private zones for all internal service discovery within a VPC; prefer DNS over hard-coded IPs.
- Public managed zones in a dedicated project with fine-grained IAM — the zone that holds your apex domain is a high-value target.
- DNSSEC: enable for any public zone you control end-to-end; requires registrar support for DS records.
- DNS Server Policy: set an inbound or outbound forwarding policy to route on-premises DNS queries or forward specific zones to an on-prem resolver.
- Cloud DNS logging: enabled on all public zones that handle prod traffic; essential for phishing and exfil detection.

## VPC Service Controls

- Create a service perimeter around sensitive GCP services (Cloud Storage, BigQuery, Cloud SQL, Secret Manager, Artifact Registry) to prevent data exfil even from compromised service accounts.
- Perimeter mode: `ENFORCED` for production; `DRY_RUN` first to identify legitimate access patterns before enforcing.
- Access levels: define IP-range-based and identity-based access levels so users with compliant devices and known IPs can cross the perimeter for legitimate work.
- Ingress and egress rules: explicitly enumerate the service accounts and services that need to cross perimeter boundaries (e.g., CI/CD pipeline SA writing to an Artifact Registry in the perimeter).

## Private Service Connect

- Use Private Service Connect (PSC) to consume managed GCP services (Cloud SQL, BigQuery, Vertex AI, Pub/Sub) from your VPC without routing traffic over the internet or through a VPC peering.
- PSC endpoint: a forwarding rule in your VPC subnet that points to the service producer's PSC endpoint address.
- For exposing your own service privately to other VPCs or organizations: publish a PSC service attachment; consumers create endpoints without knowing your internal topology.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Auto-mode VPC for a production project | Overlapping CIDRs prevent VPC peering and Shared VPC expansion later. Convert before deploying any workloads. |
| Cloud SQL or Memorystore with no authorized networks or PSC | Any IP with network access can attempt a connection. Private IP only + Auth Proxy. |
| Global Load Balancer with no Cloud Armor policy | DDoS and application-layer attacks hit origin directly. Always attach a security policy. |
| WAF rules deployed in enforce mode on day one | Legitimate traffic gets blocked before you've characterized the pattern. Preview first. |
| No VPC Flow Logs on production subnets | You're forensically blind after an incident. Flow Logs are cheap insurance. |
| Shared VPC host project `roles/editor` for service projects | Any service project SA gets full host VPC access. Grant `roles/compute.networkUser` on specific subnets only. |
| Cloud NAT without logging | Silent NAT exhaustion. ERRORS_ONLY logging is free relative to the debugging time it saves. |
| Single-region VPC for a global service | Traffic from distant regions crosses long RTTs. Deploy backend services in multiple regions behind a Global LB. |

## Security defaults

- VPC Flow Logs on all production subnets.
- Cloud Armor security policy attached to every externally exposed backend.
- No public IPs on backend compute (GKE nodes, Cloud SQL, Compute Engine that doesn't serve internet traffic).
- Private Google Access enabled on all private subnets.
- VPC Service Controls perimeter around sensitive data services in production.
- Cloud NAT for all outbound internet egress — no direct external IPs on servers.
- Private Service Connect for GCP-managed service access where available.

## Observability defaults

- Global LB: enable access logging on every backend service; push to Cloud Logging.
- Cloud Armor: enable security policy logs; alert on `preview_rate` > baseline and `block_rate` spikes.
- VPC Flow Logs: export to BigQuery or Cloud Storage via a log sink for long-term analysis.
- Cloud NAT: alert on `nat_allocation_failed` count > 0 (signals port exhaustion).
- Cloud DNS: query logs for public zones; alert on unusual query volumes (potential DNS tunneling).
- Alerting policies: LB request error rate, LB p99 latency, Cloud Armor block rate, Cloud NAT dropped packets.

## Cost considerations

- VPC Flow Logs add data processing and storage cost — use `EXCLUDE_INTERNAL_TRAFFIC` and sample at 10% for high-volume internal meshes; full sampling only on perimeter subnets.
- Cloud NAT charges per NAT IP-hour and per GB processed. Port-forward allocation matters; insufficient NAT IPs cause connection failures. Monitor `open_connections` and `sent_bytes_count`.
- Cloud Armor Standard (WAF rules) is free; Cloud Armor Managed Protection Plus (Adaptive Protection, managed threat intel) is billed. Evaluate based on threat model.
- Global Application LB: no per-hour charge for the LB itself; you pay for forwarding rules, backend traffic, and CDN cache fills. CDN offload significantly reduces origin traffic costs.
- Cross-region traffic (including inter-region VPC peering) incurs data transfer charges. Co-locate services that talk frequently in the same region.

## IaC hints

- Terraform: `google_compute_network`, `google_compute_subnetwork`, `google_compute_router` + `google_compute_router_nat`, `google_compute_global_forwarding_rule`, `google_compute_url_map`, `google_compute_backend_service`, `google_compute_security_policy` (Cloud Armor).
- VPC Service Controls: `google_access_context_manager_access_policy`, `google_access_context_manager_service_perimeter`.
- Private Service Connect: `google_compute_forwarding_rule` with `google_compute_global_address` and target `VPC_SC` for Google APIs.
- Use `google_compute_subnetwork` with `log_config` block to enable VPC Flow Logs in Terraform.

## Verification checklist

- [ ] Custom-mode VPC with non-overlapping CIDRs; auto-mode not used in prod.
- [ ] VPC Flow Logs enabled on all production subnets.
- [ ] Private Google Access on all private subnets.
- [ ] All external backends protected by a Cloud Armor security policy.
- [ ] No public IPs on non-LB compute; Cloud NAT for egress.
- [ ] Cloud DNS private zones for internal service discovery.
- [ ] VPC Service Controls perimeter covers sensitive data services.
- [ ] Cloud Armor WAF rules observed in preview before enforcement.
- [ ] LB access logs, Cloud Armor logs, and NAT allocation metrics are flowing.
