---
name: azure-networking-and-edge
description: Design or audit Azure networking — VNet, subnets, NSGs, peering, hub-spoke, Application Gateway, Azure Front Door, API Management, Private Link, Azure Firewall, ExpressRoute. Use when standing up a new VNet, exposing a service to the internet, or hardening the network perimeter.
---

# Azure Networking and Edge

## When to use

- Designing a new VNet for a subscription or workload.
- Exposing an internal service to the internet or to another VNet / subscription.
- Tuning TLS, WAF, or DDoS posture at the edge.
- Auditing east-west connectivity (VNet peering, Private Link, VPN Gateway, ExpressRoute).
- Tracing latency or cross-region egress cost.

## VNet layout — the boring default

- One VNet per environment (dev / stage / prod). Hub-spoke topology when you have more than two workload VNets or any compliance pressure — the hub VNet is the cheapest blast-radius boundary Azure gives you for centralized inspection.
- Address space: `/16` per VNet. `/24` or `/22` per subnet — leave headroom; Azure reserves 5 addresses per subnet.
- Subnets per design (not one-per-AZ like AWS — Azure subnets span all AZs in a region):
  - `snet-appgw` — Application Gateway; requires a dedicated subnet, minimum `/26`.
  - `snet-app` — application workloads (App Service VNet integration, Container Apps, AKS user pool).
  - `snet-data` — private endpoints for storage, databases, caches.
  - `snet-mgmt` — Azure Bastion or management jump services.
- IPv6 dual-stack if the workload has large-scale egress or cross-region replication needs; Azure public IPv4 charges apply for any static public IP.
- NSG Flow Logs to a Storage Account (cheap) and optionally to Traffic Analytics via Log Analytics for visibility.

## Subnet, NSG, and route table discipline

- NSGs: stateful, the primary per-subnet control. Associate one NSG per subnet; reference Azure Service Tags (`AzureLoadBalancer`, `AzureMonitor`, `Storage.EastUS`) instead of raw CIDRs for intra-Azure traffic.
- Default-deny posture: NSG inbound rule `65000 DenyAllInBound` is implicit. Add explicit allows for required traffic only. Never add an inbound allow for port 22 or 3389 to `0.0.0.0/0`.
- Application security groups (ASGs): group VMs and pods by role (ASG `asg-app`, `asg-db`) and reference ASGs in NSG rules for readable intent without CIDR fragility.
- UDRs (User Defined Routes): force-tunnel `0.0.0.0/0` via Azure Firewall in the hub for any subnet that should not have direct internet egress.

## Hub-spoke topology

- Hub VNet contains: Azure Firewall (or NVA), VPN Gateway / ExpressRoute Gateway, Azure Bastion, and shared DNS Resolver.
- Spoke VNets peer to the hub; spoke-to-spoke traffic transits the hub Firewall for inspection.
- VNet peering is non-transitive — spokes cannot reach each other without routing through the hub; this is the security invariant.
- Azure Virtual WAN is the managed alternative to hand-rolled hub-spoke when the organization has > 5 spokes or branch-office connectivity via SDWAN.

## Private Link and Private Endpoints

- Private endpoint for every PaaS service used by a production workload: Azure SQL, Cosmos DB, Blob Storage, Key Vault, Service Bus, Container Registry, Azure Monitor (via Private Link Scope).
- Private DNS zones per service (e.g., `privatelink.blob.core.windows.net`), linked to each spoke VNet — required for DNS resolution of the private endpoint IP.
- Azure Private Link Service to expose your own service to other VNets / subscriptions without peering; consumers' CIDRs stay private from you.
- Disable public network access (`publicNetworkAccess: 'Disabled'`) on every PaaS resource that has a private endpoint — don't leave the public endpoint as a backup.

## Application Gateway v2

- WAF mode: start in **Detection** mode, review logs for false positives for 72 hours on a sample of production traffic, then switch to **Prevention**.
- WAF policy: OWASP 3.2 Core Rule Set as baseline; add Microsoft Bot Manager rule set for user-facing sites.
- Backend pool: app tier in `snet-app`; Application Gateway in `snet-appgw`. Health probes must reflect real readiness (application `/healthz` endpoint, not TCP port check).
- TLS: terminate TLS at the Application Gateway; re-encrypt to the backend if end-to-end TLS is required (select the backend certificate or use a trusted CA cert). Minimum TLS 1.2 on both listener and backend.
- Autoscaling: set a `minCapacity` of 2 (for HA across fault domains) and a `maxCapacity` that covers your expected peak; Application Gateway v2 autoscales within those bounds.
- HTTP-to-HTTPS redirect listener: always present.

## Azure Front Door (Standard / Premium)

- Tier: **Premium** for private origin (Private Link to App Service / AKS / Storage), WAF with bot protection, and DDoS Network Protection. **Standard** for CDN + basic WAF + custom rules.
- Origin groups: health probe per origin group; failover threshold tuned to your SLA (default 50% unhealthy threshold is usually fine).
- WAF policy at Front Door: sovereign to the Application Gateway WAF policy. Both can coexist — Front Door WAF protects the global edge; Application Gateway WAF protects per-region ingress.
- Caching: use route-level caching rules; purge via API or `az afd endpoint purge` — avoid invalidating the entire edge cache carelessly.
- Custom domain + managed TLS: Front Door provisions and rotates the certificate; associate the CNAME in your DNS zone before Front Door will issue.

## API Management

- Tier: **Consumption** for event-driven / low-volume APIs (no VNet, per-call billing); **Developer** for non-prod; **Standard** for production; **Premium** for multi-region, VNet integration, and availability zones.
- VNet integration: **Internal** mode for APIs that should not be internet-reachable (place Front Door or Application Gateway in front); **External** mode for internet-accessible APIs with WAF layered by an upstream gateway.
- Authentication: validate JWTs via the `validate-jwt` policy at the API gateway level — never "verify in the handler".
- Throttling: `rate-limit-by-key` policy on every public product; configure `retry-after` headers so clients back off gracefully.
- Named values and Key Vault: store secrets as named values backed by Key Vault references with APIM Managed Identity — no plaintext secrets in policies.
- Diagnostics: send APIM logs and metrics to a Log Analytics workspace; instrument `request-id` header propagation for end-to-end tracing.

## Azure Firewall

- SKU: **Premium** for TLS inspection, IDPS (Intrusion Detection and Prevention), URL filtering; **Standard** for stateful L3/L4 + FQDN rules.
- Policy: use Azure Firewall Policy (not classic rules) — hierarchical policies (parent base policy + child per-spoke) scale across environments.
- Rule collection order: application rules (FQDN) → network rules (IP:port) → DNAT rules. Application rules are evaluated first by default and are preferred for egress control because they resolve FQDNs dynamically.
- Threat Intelligence: on in **Alert and Deny** mode for production; blocks known malicious IPs and domains.
- Logs: Firewall logs to Log Analytics (`AzureDiagnostics` or structured `AzureFirewallNetworkRule` / `AzureFirewallApplicationRule` tables); alert on deny events from your app subnet ranges.

## ExpressRoute

- Circuit: provision through a connectivity partner; use **ExpressRoute Global Reach** for site-to-site connectivity without routing through Azure.
- Redundancy: two circuits (primary + secondary) in different peering locations for 99.95% SLA; a single circuit is a single point of failure.
- Route filtering: use BGP communities to control which Azure public service prefixes are advertised to your on-prem routers.
- VPN Gateway fallback: configure a VPN Gateway in the same ExpressRoute gateway SKU for failback when the circuit is unavailable; set route preference so ExpressRoute is preferred.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| All workloads in a single VNet with no hub-spoke | Blast radius = everything. Hub-spoke separates environments and enables centralized inspection. |
| NSG inbound allow `Any` to `Any` "temporarily" | Never reverted. Scope to specific source ASGs or Service Tags. |
| Private endpoint DNS not linked to spoke VNets | DNS resolves to the public IP; private endpoint is bypassed silently. |
| Application Gateway WAF in Detection mode forever | Detection logs attacks but blocks none. Set a flip-to-Prevention date. |
| Azure Firewall in `Alert Only` threat intelligence mode | Known-bad IPs traverse the firewall unchecked. Set `Alert and Deny`. |
| APIM in External VNet mode with no upstream WAF | API gateway exposed directly to the internet without WAF protection. |
| ExpressRoute single circuit, no VPN fallback | Circuit maintenance window = full on-prem connectivity loss. |
| VNet peering without route table force-tunneling through Firewall | Spoke-to-spoke traffic bypasses inspection; lateral movement is undetected. |

## Security defaults

- NSG Flow Logs on for every production subnet.
- Microsoft Defender for Network (DDoS Network Protection) on for any hub VNet with internet-facing load balancers.
- Azure Firewall with threat intelligence in `Alert and Deny` mode.
- No management port (22, 3389) exposed publicly — Azure Bastion or Just-In-Time VM access.
- Private endpoints for all PaaS services; public network access disabled.
- WAF in Prevention mode for all public-facing Application Gateways and Front Door profiles after initial detection window.

## Observability defaults

- Application Gateway access logs and performance logs to Log Analytics.
- NSG Flow Logs to Storage + Traffic Analytics for topology-aware visibility.
- Azure Firewall logs (`AzureFirewallNetworkRule`, `AzureFirewallApplicationRule`) to Log Analytics; alert on deny events from app subnets.
- Front Door access logs for security-sensitive surfaces; standard metrics (request count, latency, cache hit rate) in Azure Monitor.
- Alerts on `ApplicationGateway.UnhealthyHostCount`, `BackendResponseStatus` 5xx rates, NSG `deny_count` spikes, and Firewall IDPS alerts.

## Cost considerations

- Azure Firewall is priced per deployment-hour (~$1.25/hr for Standard) plus per-GB processed — meaningful at scale. Standard SKU for simple egress control; only upgrade to Premium when IDPS is needed.
- Application Gateway v2 autoscaling charges per capacity unit (CU); set a meaningful `minCapacity` but watch for CU runaway under DDoS.
- Public IPv4 charges ~$0.005/hr per address — switch to Front Door (anycast, no per-IP charge) for internet-facing endpoints where possible.
- Cross-region VNet peering charges per GB transferred; architect services to minimize cross-region east-west traffic.
- Azure Bastion charges hourly per instance plus per-session bandwidth; use the Developer SKU for low-frequency access, Standard for teams.
- Private endpoint charges per endpoint per hour plus per-GB data processed — inexpensive relative to the security value.

## IaC hints

- Bicep: `Microsoft.Network/virtualNetworks`, `Microsoft.Network/networkSecurityGroups`, `Microsoft.Network/privateDnsZones`, `Microsoft.Network/privateEndpoints`, `Microsoft.Network/applicationGateways`.
- Terraform: `azurerm_virtual_network`, `azurerm_network_security_group`, `azurerm_private_endpoint`, `azurerm_private_dns_zone`, `azurerm_application_gateway`. Use `azurerm_subnet_network_security_group_association` to enforce NSG-subnet binding in code.
- For hub-spoke, model the hub VNet in a separate Bicep module / Terraform workspace that the spoke modules reference via outputs — keeps blast radius boundaries in the code structure too.
- Private DNS zone links are a common IaC drift source; explicitly `azurerm_private_dns_zone_virtual_network_link` for every spoke VNet.

## Verification checklist

- [ ] Subnet layout has dedicated tiers (appgw / app / data / mgmt); NSG on every subnet.
- [ ] No `0.0.0.0/0` inbound allows on any non-load-balancer NSG.
- [ ] Private endpoints deployed; public network access disabled on PaaS resources.
- [ ] Private DNS zones linked to all spoke VNets; name resolution verified from app tier.
- [ ] WAF in Prevention mode (or scheduled flip date set with detection-mode review).
- [ ] Azure Firewall or NVA in the hub inspecting east-west and egress traffic.
- [ ] NSG Flow Logs on and shipping to Traffic Analytics.
- [ ] No management ports exposed publicly; Bastion deployed and tested.
- [ ] ExpressRoute has dual circuits or VPN fallback if on-prem connectivity is required.
