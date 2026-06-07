/**
 * The 19 clouds of the blackrim-nimbus marketplace.
 *
 * `id` matches the cloud-<id> plugin directory at the repo root (a test asserts
 * the set stays in sync). `path: 'golden'` marks the golden-path deploy target,
 * lit by default in the cloud matrix while the others sit available-but-recessive.
 *
 * House style: no em-dashes anywhere in copy (a test enforces this).
 */
export const providers = [
  {
    id: 'cloudflare',
    label: 'Cloudflare',
    best: 'Edge Workers, R2, D1, Pages. The golden-path deploy target.',
    tag: 'Edge',
    path: 'golden'
  },
  {
    id: 'vercel',
    label: 'Vercel',
    best: 'Next.js, Edge Functions, ISR, KV, Blob, and Postgres.',
    tag: 'Frontend'
  },
  {
    id: 'netlify',
    label: 'Netlify',
    best: 'Builds, Edge Functions, Blobs, Forms, deploy previews.',
    tag: 'Frontend'
  },
  {
    id: 'supabase',
    label: 'Supabase',
    best: 'Postgres, Auth, RLS, Storage, Realtime, pgvector.',
    tag: 'Backend'
  },
  {
    id: 'fly',
    label: 'Fly.io',
    best: 'Machines at the edge, scale to zero, global Postgres.',
    tag: 'Edge'
  },
  {
    id: 'railway',
    label: 'Railway',
    best: 'Services, volumes, cron, and PR preview deploys.',
    tag: 'PaaS'
  },
  {
    id: 'render',
    label: 'Render',
    best: 'Web services, workers, cron, managed Postgres.',
    tag: 'PaaS'
  },
  {
    id: 'digitalocean',
    label: 'DigitalOcean',
    best: 'Droplets, App Platform, DOKS, and Spaces.',
    tag: 'Cloud'
  },
  {
    id: 'aws',
    label: 'AWS',
    best: 'Lambda, ECS, and the deep well-architected core.',
    tag: 'Hyperscale'
  },
  {
    id: 'gcp',
    label: 'GCP',
    best: 'Cloud Run, GKE, BigQuery, global networking.',
    tag: 'Hyperscale'
  },
  {
    id: 'azure',
    label: 'Azure',
    best: 'App Service, AKS, Functions, enterprise identity.',
    tag: 'Hyperscale'
  },
  {
    id: 'oci',
    label: 'OCI',
    best: 'Compute, OKE, Autonomous Database, generous egress.',
    tag: 'Enterprise'
  },
  {
    id: 'ibm',
    label: 'IBM Cloud',
    best: 'VPC, Code Engine, OpenShift, and watsonx.',
    tag: 'Enterprise'
  },
  {
    id: 'linode',
    label: 'Linode',
    best: 'Compute, LKE, object storage, managed databases.',
    tag: 'Cloud'
  },
  {
    id: 'vultr',
    label: 'Vultr',
    best: 'Cloud compute, bare metal, VKE, block storage.',
    tag: 'Cloud'
  },
  {
    id: 'hetzner',
    label: 'Hetzner',
    best: 'Cloud servers and Robot dedicated, price per core.',
    tag: 'Cloud'
  },
  {
    id: 'scaleway',
    label: 'Scaleway',
    best: 'EU residency, Kapsule, serverless containers.',
    tag: 'EU'
  },
  {
    id: 'alibaba',
    label: 'Alibaba Cloud',
    best: 'ECS, ACK, Function Compute, APAC and China.',
    tag: 'APAC'
  },
  {
    id: 'tencent',
    label: 'Tencent Cloud',
    best: 'CVM, TKE, SCF, COS, APAC and China.',
    tag: 'APAC'
  }
];

/**
 * The golden path: vite + voidzero + cloudflare + convex. The build chain plus
 * the deploy target plus the data layer. Cloudflare is the one cloud in the
 * matrix; voidzero and convex are the toolchain and backend around it.
 */
export const goldenStack = [
  {
    step: '01',
    name: 'Vite',
    role: 'Scaffold',
    note: 'npm create vite. Instant dev server, first-class TypeScript, the front door to the toolchain.'
  },
  {
    step: '02',
    name: 'voidzero',
    role: 'Build',
    note: 'Vite, Rolldown, and Oxc: one Rust-grade toolchain that lints, bundles, and tests.'
  },
  {
    step: '03',
    name: 'Cloudflare',
    role: 'Deploy',
    note: 'wrangler deploy ships to Workers and Pages at the edge, live in seconds, global by default.'
  },
  {
    step: '04',
    name: 'Convex',
    role: 'Data',
    note: 'convex deploy gives you a reactive, typed backend: queries, mutations, and live state.'
  }
];
