---
name: azure-observability-and-cost
description: Wire up or audit Azure observability and cost — Azure Monitor, Application Insights, Log Analytics, diagnostic settings, Cost Management + Billing, Azure Advisor, Reservations, Savings Plans, Spot scheduling. Use when adding telemetry, tracking down a regression, or shrinking an Azure bill.
---

# Azure Observability and Cost

## When to use

- Setting up metrics, logs, and traces for a new Azure service.
- Building an SLO dashboard or wiring an alert to an on-call channel.
- Diagnosing a latency, error-rate, or cost regression.
- Negotiating a Reservation or Savings Plan commitment.
- Running a quarterly cloud cost review.

## Observability pillars

| Pillar | Service |
| --- | --- |
| Metrics | Azure Monitor Metrics + platform metrics per resource |
| Logs | Log Analytics workspace (KQL query surface) |
| Traces | Application Insights (auto-instrumentation) or OpenTelemetry → Azure Monitor OTLP endpoint |
| Synthetics | Application Insights Availability Tests (URL ping, multi-step) |
| Real user monitoring | Application Insights JavaScript SDK or the Browser SDK |
| Service map | Application Insights Application Map (dependency topology) |

## Defaults — every service

- Structured JSON logs with a stable `operationId` / correlation ID field shared across the request chain.
- Application Insights SDK or auto-instrumentation for request rate, failure rate, and response time — the three core signals. Use `TelemetryClient` or the OpenTelemetry Azure Monitor exporter.
- Distributed tracing on, with the `traceparent` W3C header propagated end-to-end across microservices.
- At least one alert per service tied to user-visible pain (HTTP 5xx rate, p95 response time, queue backlog, dead-letter count). Avoid alerting on raw CPU utilization alone.
- Log retention: 30 days interactive (hot) in Log Analytics; extend to 90 days for security logs; ship to a Storage Account for archive retention > 90 days. The default 30-day retention is not an unbounded bill, but a 90-day retention upgrade costs ~$0.10/GB/mo and is worth it for incident investigations.
- Diagnostic settings: every Azure resource must have a diagnostic setting routing logs and metrics to the central Log Analytics workspace. Enforce via Azure Policy.

## Log Analytics workspace design

- One workspace per environment (dev / stage / prod) is the simplest model. A centralized cross-subscription workspace is preferred when Sentinel is active or when Security Operations needs a single query pane.
- Avoid too many workspaces: cross-workspace queries (`workspace()` function in KQL) work but add latency and complexity.
- Data ingestion plan: **Analytics** plan for actively queried data; **Basic** plan for verbose diagnostic logs that are rarely queried but needed for compliance (reduces cost ~75% vs Analytics at the expense of limited query capability).
- Commitment tiers: at 100+ GB/day ingestion, commitment tiers (100 GB, 200 GB, ...) are significantly cheaper than pay-as-you-go — calculate the break-even and buy the appropriate tier.
- Table retention per table: set different retention on noisy tables (e.g., `AzureDiagnostics` from verbose sources) vs security tables (`SecurityEvent`, `SigninLogs`).

## Alerts — write them like contracts

Good alert spec:
- **Signal:** which metric or KQL query result, at which threshold, over which evaluation window.
- **Severity:** 0 (critical, immediate page) through 4 (informational). Use 0 and 1 sparingly.
- **Action group:** which email / SMS / webhook / ITSM connector / Logic App automation fires.
- **Runbook:** URL in the alert description — first thing the responder reads.

Bad alerts: static thresholds on volatile metrics, alerts that fire and auto-resolve without human action, duplicate alerts for the same failure mode.

Dynamic thresholds (ML-based adaptive alerting) for metrics that have a predictable daily pattern (request rate, queue depth); static thresholds for metrics with clear hard limits (disk full prediction, certificate expiry countdown).

## Application Insights

- Auto-instrumentation: available for App Service (Windows / Linux), Azure Functions, and Container Apps without code changes — enable via the Application Insights blade on the resource.
- SDK instrumentation: for AKS workloads and custom runtimes, use the Azure Monitor OpenTelemetry exporter (`azure-monitor-opentelemetry` for Python/Node; `Azure.Monitor.OpenTelemetry.Exporter` for .NET).
- Sampling: adaptive sampling is on by default in the SDK — it automatically reduces telemetry volume at high request rates. For regulated or security-sensitive workloads, use fixed-rate sampling with a high rate (10–100%) and sample at the application level.
- Custom events and metrics: emit domain-level events (`telemetryClient.trackEvent("OrderPlaced", ...)`) for business KPIs visible alongside infrastructure metrics.
- Availability tests: at minimum, a URL ping test from 5 geographic locations to the public health endpoint; multi-step tests for authenticated flows.

## Dashboards

- One Azure Monitor Workbook per service, one per environment.
- Top section: SLI metrics (availability, latency, error rate). Middle: dependency health (upstream latency, downstream error rate). Bottom: capacity and queue depth.
- Parameterized workbooks (subscription, resource group, time range) so the same template covers all environments.
- Persist workbooks in ARM / Bicep so they survive subscription moves and are version-controlled.

## Cost — the actual playbook

### Visibility

- **Cost Management + Billing** with cost allocation tags (`Environment`, `Service`, `Owner`, `CostCenter`) enforced via Azure Policy `require-tag-on-resource-group` and `inherit-tag-from-resource-group`.
- **Cost anomaly alerts**: configure per-subscription and per-resource-group anomaly alerts — they surface unknown-unknowns within 24 hours.
- **Budgets**: per-subscription budget alert at 80% (warning) and 100% (action); per-resource-group budget for high-spend services; budget actions can trigger Logic App automation (e.g., stop a Synapse pool).
- **Azure Advisor cost recommendations**: reviewed weekly during the team's sprint planning; Advisor surfaces Reserved Instance and Savings Plan opportunities based on actual usage.
- **Export to Storage**: Cost Management export (daily, CSV) to a storage account + Power BI or Synapse for custom slicing beyond what the portal provides.

### Optimization levers

| Lever | Where it pays |
| --- | --- |
| Azure Reservations (1-year, no upfront) | VMs, AKS node pools, Azure SQL, Cosmos DB, App Service plans — 20–60% vs pay-as-you-go. |
| Azure Savings Plans for compute | Flexible commitment across VMs, Functions, Container Apps — 15–50% without locking to specific SKUs. |
| Spot VMs | Stateless / batch / AKS spot node pools — 60–90% off on-demand price. |
| Azure Advisor right-size recommendations | Over-provisioned VMs, App Service plans, SQL DTUs. |
| Dev/test subscription pricing | 30–55% off for non-production workloads; requires Visual Studio or EA/MCA dev/test offer. |
| Auto-shutdown for dev VMs and AKS clusters | Friday-evening scheduled stop; saves 60+ hours of compute per week. |
| Log Analytics commitment tier | Predictable ingestion > 100 GB/day should use commitment pricing. |
| Pause Synapse dedicated SQL pool | Compute paused = no compute charges; storage still billed. |
| Azure Hybrid Benefit | Windows Server and SQL Server licenses already owned can be applied to Azure VMs and SQL MI. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Log Analytics workspace with infinite retention for all tables | All-Analytics plan + long retention = large bill for logs never queried. Use Basic plan for verbose sources. |
| No cost allocation tags | Cost reports are meaningless when the bill spikes. Tag everything before first deploy. |
| All-static alert thresholds on request-rate metrics | 3 AM false positive storm from normal daily low traffic pattern. Use dynamic thresholds. |
| Reservations bought before usage stabilizes | Stranded commitment for 1–3 years. Wait 30 days of stable usage data first. |
| Application Insights sampling off for high-traffic services | Telemetry ingestion costs spiral; sampled data is fine for most analysis at high volume. |
| Azure Monitor alert action groups with no runbook link | On-call engineer sees the alert, has no context, spends 15 minutes finding where to look. |
| Synapse dedicated SQL pool never paused in dev | $1.50/DWU100c/hr × 730 hr/month × 2 dev pools = a meaningful line item for idle capacity. |

## Observability + cost together

The cheapest debugging is the alert that points directly to the runbook. The most expensive debugging is the missing dashboard during a 2 AM incident. Invest in telemetry upfront; cut elsewhere.

Common false economies:

- Disabling Application Insights to save ingestion cost — engineers spend 3× more time on each incident without traces.
- Over-sampling telemetry — the one failing request you sampled away was the one you needed.
- Single shared Log Analytics workspace without table-level retention — security and operational logs treated identically when they have different retention needs.

## IaC hints

- Bicep: `Microsoft.Insights/components` for Application Insights (link to a Log Analytics workspace via `workspaceResourceId`); `Microsoft.Insights/metricAlerts` and `Microsoft.Insights/scheduledQueryRules` for alerts; `Microsoft.OperationalInsights/workspaces` for Log Analytics.
- Terraform: `azurerm_application_insights` with `workspace_id` set; `azurerm_monitor_metric_alert`, `azurerm_monitor_scheduled_query_rules_alert_v2`; `azurerm_log_analytics_workspace` with `retention_in_days` always set.
- Action groups (`azurerm_monitor_action_group`) and alert rule → action group association belong in the monitoring module, separate from compute — they outlive individual services.
- Diagnostic settings (`azurerm_monitor_diagnostic_setting`) should be managed in the same module as the resource they instrument, not in a separate "monitoring" sweep — co-location makes it clear which settings belong to which resource.

## Verification checklist

- [ ] Every service emits structured logs, platform metrics, and distributed traces with a shared correlation ID.
- [ ] Diagnostic settings on every resource routing to the central Log Analytics workspace.
- [ ] Log retention bounded per table; verbose/diagnostic tables on Basic ingestion plan.
- [ ] At least one alert per service ties to a user-visible failure mode, with a linked runbook.
- [ ] Tagging policy enforced; Cost Management slices match expected service / env breakdown.
- [ ] Advisor cost recommendations reviewed; right-size actions tracked in backlog.
- [ ] Reservation / Savings Plan coverage reviewed after 30 days of stable usage.
- [ ] Dashboards / Workbooks exist for top services and are stored in IaC.
- [ ] Budget alerts at 80% and 100% with action group routing to a real channel.
- [ ] Application Insights availability tests covering every public-facing endpoint.
