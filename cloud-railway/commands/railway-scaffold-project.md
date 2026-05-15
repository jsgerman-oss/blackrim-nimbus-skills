---
description: Scaffold a Railway project — railway.json, Dockerfile (or Nixpacks config), environment splits (development / staging / production), GitHub Actions deploy job with Service Token, Postgres Plugin wiring via Reference Variables, and PR preview environment setup.
argument-hint: <workload-description>
---

# Railway Scaffold Project

Scaffold a new Railway project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the build strategy.** Recommend based on the workload description and ask the user to confirm:
   - **Nixpacks (recommended):** Repo uses a recognized language/framework (Node, Python, Go, Ruby, Rust, etc.) with no unusual OS dependencies. Zero config; Railway auto-detects.
   - **Dockerfile:** App has OS-level dependencies, a multi-stage build, or a non-standard runtime. Include a production-hardened multi-stage Dockerfile.
   - **Docker image:** Pre-built image already exists. Ask for the registry path and tag policy.

2. **Confirm scope** with up to three questions if not obvious:
   - Does this project need a Postgres database from day one, or is that future work?
   - How many environments are needed (just production, or development + staging + production)?
   - Is GitHub the source of truth for auto-deploys, or will deploys be triggered manually or from another CI system?

3. **Generate the project scaffold** in the current working directory. Every scaffold must include:
   - `railway.json` with health check, restart policy, and start command.
   - A `.gitignore` covering Railway artifacts.
   - Environment variable documentation (`env.example`) listing every variable with a description.
   - GitHub Actions workflow for CI → deploy.
   - A `README.md` with Railway-specific bootstrap and deploy instructions.

4. **Wire production-grade defaults:**
   - Health check endpoint (`/health`) returning 200 when the service is genuinely ready.
   - `restartPolicyType: ON_FAILURE` for web services.
   - Postgres connection via Reference Variable, not hardcoded URL.
   - Service Token in GitHub Actions Secrets (document where to set it, don't generate the token value).
   - Resource limits documented (set in Railway dashboard after deploy, referenced in README).

5. **Print next steps** — the exact sequence of CLI and dashboard actions needed after running this scaffold.

## Project layout

### Common files (all projects)

```text
.
├── railway.json              # Build + deploy config for Railway
├── .gitignore                # Covers node_modules, __pycache__, .env, etc.
├── env.example               # All required env vars with descriptions (no secret values)
├── .github/
│   └── workflows/
│       ├── deploy.yml        # Deploy to Railway on push to main
│       └── preview.yml       # Deploy preview env on PR open; cleanup on close
└── README.md                 # Bootstrap + deploy instructions
```

### Web service additions (Nixpacks build)

```text
.
├── railway.json
└── nixpacks.toml             # Only if language version or apt packages need pinning
```

### Web service additions (Dockerfile build)

```text
.
├── railway.json
└── Dockerfile                # Multi-stage, non-root user, minimal final image
```

## Generated files

### `railway.json`

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "node dist/server.js",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

Adjust `startCommand` for the detected language (`python server.py`, `./my-service`, etc.) and `builder` to `"DOCKERFILE"` if using a Dockerfile.

### `Dockerfile` (multi-stage, if Dockerfile build selected)

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine AS runner
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
WORKDIR /app
COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "dist/server.js"]
```

Tailor for the language/framework — Go produces a static binary, Python uses a virtualenv, etc.

### `env.example`

```bash
# === Required: set in Railway Variables panel ===
# Database (set via Reference Variable in Railway, not manually)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# App secret key — generate with: openssl rand -hex 32
SECRET_KEY=<generate-a-secret>

# External API key
STRIPE_SECRET_KEY=<from-stripe-dashboard>

# === Set automatically by Railway ===
PORT=                    # Railway sets this; bind to $PORT in your app
RAILWAY_ENVIRONMENT=     # 'production', 'staging', 'development'
RAILWAY_SERVICE_NAME=    # Service name from Railway dashboard
```

### `.github/workflows/deploy.yml`

```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

concurrency:
  group: railway-production
  cancel-in-progress: false

jobs:
  deploy:
    name: Deploy (production)
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli@latest

      - name: Deploy
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_PRODUCTION }}
        run: |
          railway up \
            --service ${{ vars.RAILWAY_SERVICE_NAME }} \
            --environment production \
            --detach
```

### `.github/workflows/preview.yml`

```yaml
name: Railway Preview Environments

on:
  pull_request:
    types: [opened, synchronize, reopened, closed]

jobs:
  deploy-preview:
    name: Deploy PR preview
    runs-on: ubuntu-latest
    if: github.event.action != 'closed'

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli@latest

      - name: Deploy to preview environment
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_STAGING }}
        run: |
          railway up \
            --service ${{ vars.RAILWAY_SERVICE_NAME }} \
            --environment "pr-${{ github.event.pull_request.number }}" \
            --detach

  cleanup-preview:
    name: Delete PR preview
    runs-on: ubuntu-latest
    if: github.event.action == 'closed'

    steps:
      - name: Install Railway CLI
        run: npm install -g @railway/cli@latest

      - name: Delete preview environment
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_STAGING }}
        run: |
          railway environment delete \
            --name "pr-${{ github.event.pull_request.number }}" \
            --yes || echo "Environment already deleted or not found"
```

### Health check endpoint (example for Node/Express)

```javascript
// Add to your Express app before other routes
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', ts: new Date().toISOString() });
});
```

## Postgres wiring (if database is in scope)

1. Add a Postgres Plugin to the Railway project via the dashboard.
2. In the web service's Variables panel, add:

   ```text
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

3. Configure SSL in your ORM / client:

   ```text
   # Node (pg)
   DATABASE_URL=${{Postgres.DATABASE_URL}}?sslmode=require

   # Prisma: datasource db { url = env("DATABASE_URL") }
   # + DATABASE_URL already includes SSL params from Railway Plugin
   ```

4. Run migrations as a one-shot service with `restartPolicyType: NEVER` or via `railway run`:

   ```bash
   railway run --service my-api -- npm run migrate
   ```

## Next steps (print these after scaffolding)

**One-time Railway project setup:**

1. Create a Railway account at `railway.app` and install the CLI: `npm install -g @railway/cli`
2. Log in: `railway login`
3. Create a new project: `railway init` or via the Railway dashboard.
4. Link this directory: `railway link`
5. Add environments in the Railway dashboard: `production`, `staging`, `development`.
6. Add a Postgres Plugin to each environment that needs a database.

**GitHub Actions setup:**

1. Create Service Tokens in Railway dashboard → Service → Settings → Service Tokens:
   - `RAILWAY_TOKEN_PRODUCTION` — scoped to the web service in the production environment.
   - `RAILWAY_TOKEN_STAGING` — scoped to the web service in the staging environment.
2. Add those tokens to GitHub Actions Secrets (repo Settings → Secrets and variables → Actions).
3. Add `RAILWAY_SERVICE_NAME` as a GitHub Actions Variable (not a secret) with your Railway service name.
4. Enable PR environments in Railway dashboard → Project Settings → "PR Environments".

**First deploy:**

```bash
railway up --service my-api --environment development
railway logs --service my-api
```

Verify the health check returns 200, then promote to staging and then production.

## Advice after scaffolding

- Hand off to `railway-architect` for a pre-launch review before sending real user traffic.
- Run `railway-security-reviewer` after the first staging deploy to verify Variable scope and token hygiene.
- Set a Railway spending limit in Billing Settings before the first production deploy (Pro plan).
- Subscribe to Railway's status page (`status.railway.app`) for platform incident awareness.
