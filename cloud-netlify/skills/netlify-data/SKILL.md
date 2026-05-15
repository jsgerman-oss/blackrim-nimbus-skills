---
name: netlify-data
description: Design or implement Netlify's data layer — Netlify Blobs (persistent key-value storage, deploy-scoped vs site-wide), Forms (spam mitigation, reCAPTCHA, Akismet), Netlify Connect (Enterprise data caching layer), and third-party integrations (Supabase, Auth0, Stripe). Use when adding persistent state to a JAMstack site, wiring up a contact form, or choosing between Netlify-native data and an external database.
---

# Netlify Data

## When to use

- Choosing between Netlify Blobs and an external database for site state.
- Adding a contact or subscription form without a backend server.
- Configuring spam protection on a Netlify Form.
- Understanding Netlify Connect for Enterprise data caching.
- Wiring a Netlify site to Supabase, Auth0, or Stripe.
- Auditing data persistence posture across deploys.

## Netlify Blobs

Blobs are Netlify's managed key-value store. Data persists at rest and survives deploys. Think of it as a simple object store — not a relational database, not a full document database.

### Site-wide vs deploy-scoped stores

| Store type | Scope | Persists after new deploy? | Use for |
| --- | --- | --- | --- |
| Site-wide (`getStore("name")`) | All deploys of a site | Yes | Shared state, counters, cached data, session tokens |
| Deploy-scoped (`getStore({ name, deployScoped: true })`) | One deploy only | No — wiped on next deploy | Build-time data that's per-release (generated at build, read at runtime) |

```javascript
import { getStore } from "@netlify/blobs";

// Site-wide (persists)
const cache = getStore("api-cache");
await cache.set("products", JSON.stringify(data), { ttl: 3600 }); // 1-hour TTL
const raw = await cache.get("products");
const parsed = await cache.get("products", { type: "json" }); // auto-parse JSON

// List keys with a prefix
const { blobs } = await cache.list({ prefix: "user-" });

// Deploy-scoped (cleared on new deploy)
const deployCache = getStore({ name: "build-data", deployScoped: true });
```

Available from Netlify Functions, Edge Functions, and at build time (in a Build Plugin).

### Blob data types

`store.get()` `type` options: `"text"` (default), `"json"`, `"arrayBuffer"`, `"stream"`. Use `"json"` for structured data to avoid manual `JSON.parse()`.

`store.set()` accepts a string, `ArrayBuffer`, `Blob`, or `ReadableStream`. For binary data (images, PDFs), store as `ArrayBuffer`.

### Blob limits

- Maximum blob size: **5 GB** per blob.
- No hard limit on number of keys per store.
- Latency: Blobs are backed by a geo-distributed store; reads are fast (< 100 ms globally for small values).
- Blobs are not a substitute for a transactional database — no atomicity guarantees beyond individual `get`/`set` operations.

### Blob access control

Blobs are not directly accessible from the browser. All access goes through your Functions or Edge Functions. There is no public Blobs URL (intentional). If you need public-read access, serve via a Function that reads from Blobs.

**When Blobs fit:**
- Caching external API responses for a short TTL.
- Storing per-user preferences without a database.
- Passing build-time data to runtime (deploy-scoped store written in a Build Plugin, read in a Function).
- Feature flags stored as Blob values, updated via an admin Function.

**When Blobs don't fit:**
- Relational queries, joins, or complex filtering.
- High-write-concurrency workloads (no optimistic locking / transactions).
- More than a few thousand distinct keys with complex access patterns — use Supabase, PlanetScale, or similar.

## Netlify Forms

Forms provide server-side form processing without a backend function. Netlify intercepts the form submission at the CDN layer, stores it, and can forward it to email, Slack, or a webhook.

### Enabling a form

Add `netlify` attribute (or `data-netlify="true"`) to your HTML form:

```html
<form name="contact" method="POST" data-netlify="true">
  <input type="hidden" name="form-name" value="contact" />
  <input type="text" name="name" />
  <input type="email" name="email" />
  <textarea name="message"></textarea>
  <button type="submit">Send</button>
</form>
```

For JavaScript-rendered forms (React, Vue, etc.), submit via `fetch` with `application/x-www-form-urlencoded` or `multipart/form-data`, and include a hidden HTML form in the initial render so Netlify can detect and register it at deploy time.

### Spam mitigation

**Honeypot field** (free, invisible to humans):

```html
<form name="contact" netlify netlify-honeypot="bot-field">
  <p style="display:none">
    <label>Don't fill this out: <input name="bot-field" /></label>
  </p>
  <!-- real fields -->
</form>
```

**reCAPTCHA v2** (Netlify-managed, no separate Google account required for basic use):

```html
<form name="contact" netlify netlify-recaptcha="true">
  <div data-netlify-recaptcha="true"></div>
  <!-- real fields -->
</form>
```

Netlify auto-injects reCAPTCHA at the CDN layer. If you want reCAPTCHA v3 or hCaptcha, integrate via a Function instead of relying on Netlify Forms spam protection.

**Akismet** (Pro+): Enable via the Netlify dashboard Forms settings → Spam filters. Akismet analyzes submission content for spam patterns.

### File uploads via Forms

Set `enctype="multipart/form-data"` on the form and add a file input. Netlify stores attachments with the submission. Access them via the Netlify dashboard or API. Maximum upload size per form: 10 MB.

### Form notifications

Configure under **Site configuration → Forms → Form notifications**:

- Email notifications: on submission (with field values in the email).
- Slack notifications via webhook.
- Outgoing webhook (HTTP POST to any URL) — use this to push submissions to your CRM, database, or ticketing system.

```
POST https://your-api.example.com/webhook/form-submission
Content-Type: application/json
{
  "form_id": "...",
  "form_name": "contact",
  "data": { "name": "...", "email": "...", "message": "..." }
}
```

### Form limits

| Plan | Submissions/month |
| --- | --- |
| Starter | 100 |
| Pro | 1,000 |
| Enterprise | Custom |

For high-volume forms, skip Netlify Forms and use a Function that writes directly to your database or a form SaaS (Typeform, Formspark, Staticforms).

## Netlify Connect (Enterprise)

Netlify Connect is an Enterprise-tier data layer that caches data from CMSes, commerce platforms, and custom APIs into a unified GraphQL API. It enables faster builds by centralizing data fetching and providing incremental cache invalidation.

Key facts:
- Not available on Starter or Pro plans — Enterprise only.
- Acts as a data mesh / BFF (Backend for Frontend) — your build fetches from Connect's GraphQL endpoint instead of each upstream CMS API directly.
- Supports: Contentful, Contentstack, Sanity, Shopify, custom REST/GraphQL sources.
- Cache invalidation via webhook from the upstream source.

For teams not on Enterprise, the equivalent pattern is a Build Plugin that fetches and caches data into deploy-scoped Blobs at build time.

## Third-party integrations

### Supabase

Supabase (PostgreSQL + auth + storage) is a natural complement to Netlify for full-stack JAMstack apps. The Netlify × Supabase integration (available via the Netlify dashboard Extensions marketplace) automatically:

- Provisions a Supabase project on site creation.
- Injects `SUPABASE_URL` and `SUPABASE_ANON_KEY` as environment variables.
- Wires Netlify Identity JWT secrets to Supabase row-level security policies.

Manual integration:

```javascript
// netlify/functions/db.js
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY  // server-side only — never expose to the browser
);

export const handler = async (event) => {
  const { data, error } = await supabase.from("posts").select("*");
  // ...
};
```

`SUPABASE_SERVICE_ROLE_KEY` must be scoped to `Functions` environment only — never `Runtime` (browser-exposed).

### Auth0

Auth0 integration via Netlify's Auth0 extension auto-injects `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, and `AUTH0_CLIENT_SECRET`. Use the Auth0 Next.js / SvelteKit SDK for the frontend; verify JWTs in Functions using the Auth0 JWT verifier library.

### Stripe

Stripe webhooks work naturally with Netlify Functions:

```javascript
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

export const handler = async (event) => {
  const sig = event.headers["stripe-signature"];
  let stripeEvent;
  try {
    stripeEvent = stripe.webhooks.constructEvent(event.body, sig, webhookSecret);
  } catch (err) {
    return { statusCode: 400, body: "Webhook signature verification failed" };
  }
  // handle stripeEvent.type
};
```

`STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` scoped to `Functions` only.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using Blobs as a relational database | No joins, no transactions, no indexing — performance cliffs and consistency bugs at scale. |
| Netlify Forms for high-volume or sensitive PII | 100-submission Starter limit and no field-level encryption. Build a Function + database pipeline. |
| Exposing `SUPABASE_SERVICE_ROLE_KEY` in a `Runtime` env var | Every browser request includes this key; full DB access for anyone who opens DevTools. |
| Skipping honeypot or reCAPTCHA on public forms | Spam bots fill forms within minutes of site launch. |
| Deploy-scoped Blobs for user-generated data | Data is wiped on every deploy. Any user-written value is lost on the next push. |
| Building Netlify Connect patterns from scratch on Starter | Duplicated API calls on every build, no cache invalidation, slow builds. Evaluate the plan cost vs eng time. |

## Security defaults

- Blob values are not encrypted at the application layer by default. For sensitive values (tokens, PII), encrypt before `store.set()` and decrypt after `store.get()` using `crypto.subtle` (available in both Functions and Edge Functions).
- Forms: enable honeypot on every form, regardless of expected bot traffic. Enable reCAPTCHA for any form that feeds real business data (contact, sign-up, waitlist).
- Database credentials (Supabase service role, Stripe secret key): scope to `Functions` environment, never `Build` or `Runtime`.
- Never store raw credit card numbers or passwords in Blobs — use Stripe Tokens / SetupIntents and your auth provider's hashed credential storage.

## Observability defaults

- Log Blob read/write operations at the Function level with key name, duration, and result status.
- Monitor Forms spam filter hit rate via the dashboard Forms → Spam submissions view.
- Track Blob store growth (key count, data volume) if using it as a primary cache — unchecked growth becomes a cost issue on future paid Blobs tiers.
- Webhook delivery failures (Stripe, external webhooks for Forms): implement retry logic in your handler; log raw payload on failure for replay.

## Cost considerations

- Blobs pricing: as of 2026, included in all plans with generous limits; large-scale binary blob storage may incur add-on costs — check current pricing dashboard.
- Forms overage: 100/month on Starter; $19/month for 1,000 additional submissions (check current rates). For anything beyond a simple contact form, a Function + database is almost always cheaper.
- Netlify Connect: Enterprise-only pricing; evaluate against the engineering cost of building your own data layer.
- Third-party integrations (Supabase, Auth0, Stripe) bill independently — Netlify has no involvement in their costs.

## IaC hints

- Blobs configuration is implicit (no `netlify.toml` stanza needed). The `@netlify/blobs` package is the only dependency.
- Forms are detected at build time from the static HTML — no `netlify.toml` config, but the `data-netlify="true"` attribute must be present in the rendered HTML that Netlify indexes.
- Environment variables for integrations: manage via `netlify env:set KEY VALUE --context functions` or the Netlify dashboard.
- The community Terraform `netlify/netlify` provider does not yet support Blobs or Forms configuration — manage these through the CLI or dashboard.

## Verification checklist

- [ ] Blob store type (site-wide vs deploy-scoped) matches the data's intended lifetime.
- [ ] Sensitive Blob values encrypted at the application layer before storage.
- [ ] Forms have at least a honeypot field; reCAPTCHA enabled for business-critical forms.
- [ ] Form submission notifications routed to a real team channel (not just the default Netlify email).
- [ ] Database credentials (Supabase service role, Stripe secret) scoped to `Functions` env only.
- [ ] High-volume form scenario analyzed: 100/month Starter limit respected or upgrade path documented.
- [ ] Blobs not used for relational or transactional data without a documented consistency tradeoff.
