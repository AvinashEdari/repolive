# Deployment

Stage 8 remains disabled by default. Before enabling it, configure the server-only variables listed
in `ENVIRONMENT.md`, apply migration `0004_saas_foundation`, register the Stripe webhook at
`/api/v1/billing/webhook`, and restrict GitHub App permissions to Metadata read and Contents read.
Never place Stripe, analytics, API pepper, admin subjects, or GitHub App private-key values in
Vercel or any `NEXT_PUBLIC_` variable. Billing and private repositories are not live until the
corresponding sections of `RELEASE_CHECKLIST.md` pass.

Stage 8 remains disabled by default. Before enabling it, configure the server-only variables listed
in `ENVIRONMENT.md`, apply migration `0004_saas_foundation`, register the Stripe webhook at
`/api/v1/billing/webhook`, and restrict GitHub App permissions to Metadata read and Contents read.
Never place Stripe, analytics, API pepper, admin subjects, or GitHub App private-key values in
Vercel or any `NEXT_PUBLIC_` variable. Billing and private repositories are not live until the
corresponding sections of `RELEASE_CHECKLIST.md` pass.

The staging stack was deployed and validated on 2026-08-11:

- Frontend: `https://repolive-web.vercel.app` (Vercel)
- Backend: `https://repolive-api.onrender.com` (Render)
- Database and authentication: Supabase PostgreSQL and Supabase Auth

The following procedure remains the deployment checklist for a replacement staging or production
environment. Provider credentials and database secrets are intentionally not stored in this
repository.

1. Create a Supabase/PostgreSQL database and obtain its server-side connection URL.
2. Set `APP_ENV=production`, a `postgresql+psycopg://` `DATABASE_URL`, HTTPS `WEB_ORIGIN`, explicit
   `ALLOWED_HOSTS`, `SUPABASE_URL`, a new `ANALYSIS_VERSION`, and optionally a server-only
   `GITHUB_TOKEN`.
3. From `apps/api`, run `python -m alembic -c alembic.ini upgrade head` against that database.
4. Build and deploy the FastAPI service without exposing `.env` or repository tokens.
5. Enable Supabase email/password Auth and configure its allowed redirect URLs. Set
   `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and the browser-safe Supabase anon key,
   then run `npm run build:web` and deploy the Next.js application. Never expose a service-role key.
6. Add platform-level rate limiting, request logging with credential redaction, database backups,
   monitoring, TLS, and secret rotation before public launch.
7. Run backend/frontend suites and a public-repository smoke test in the deployed environment.

## Staging database and authentication validation

Use a dedicated staging project and test account. Never run downgrade validation against production.

1. Give the API and Alembic process the staging `DATABASE_URL`; keep it server-only.
2. Run `alembic upgrade head`, inspect tables, keys, indexes, and the foreign-key cascade, then
   exercise create, cached read, history link, history removal, and readiness operations.
3. If staging data is disposable or backed up, downgrade one revision, verify the expected schema,
   and immediately upgrade back to `head`.
4. Configure the browser with only the project URL and anon key. Create a dedicated test user,
   confirm email if required, and verify sign-up, invalid login, login, token refresh, logout, and
   invalid/expired-session behavior.
5. Analyze a small public repository anonymously and while signed in. Verify cache reuse, private
   history ownership with two test users, and an unauthenticated public share URL.
6. Remove test accounts and staging records according to the project retention policy.

Record the project, migration revision, test time, and outcomes without recording passwords,
access tokens, connection strings, or service-role credentials.

## Recommended staging shape

- Next.js: Vercel project rooted at `apps/web`.
- FastAPI: Render web service using the checked-in `render.yaml`.
- Database: Supabase PostgreSQL direct/server connection string with TLS required.

Configure the Vercel project with repository root directory `apps/web`. Keep the Render Blueprint
at the repository root; its service `rootDir` is already `apps/api`. Do not add a proxy or change
the application architecture solely for staging.

## Exact environment-variable matrix

### Supabase project

Supabase produces or controls these values. Copy values through provider dashboards, never through
source control.

| Variable or setting | Classification | Required | Consumer |
| --- | --- | --- | --- |
| PostgreSQL connection string → `DATABASE_URL` | Backend-only secret | Yes | Render and Alembic |
| Project URL → `SUPABASE_URL` | Backend-only configuration | Yes | Render JWT verifier |
| Project URL → `NEXT_PUBLIC_SUPABASE_URL` | Public frontend | Yes for auth | Vercel |
| Anon/publishable key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public frontend | Yes for auth | Vercel |
| JWT audience → `SUPABASE_JWT_AUDIENCE` | Backend-only configuration | Yes | Render; normally `authenticated` |
| Auth Site URL | Supabase dashboard setting | Yes | Exact staging frontend origin |
| Auth Redirect URLs | Supabase dashboard setting | As needed | Exact staging callback/origin URLs |

RepoLive does not use a Supabase service-role key. Prefer the Supabase session pooler when Render
requires IPv4 connectivity; use the connection URI exactly as supplied and retain TLS parameters.

### Render backend

| Variable | Classification | Required | Recommended staging value |
| --- | --- | --- | --- |
| `APP_ENV` | Backend-only configuration | Yes | `production` |
| `DATABASE_URL` | Backend-only secret | Yes | Supabase PostgreSQL/Supavisor URI |
| `WEB_ORIGIN` | Backend-only configuration | Yes | Exact Vercel staging origin, HTTPS, no path |
| `ALLOWED_HOSTS` | Backend-only configuration | Yes | Exact Render API hostname, no scheme/path/wildcard |
| `SUPABASE_URL` | Backend-only configuration | Yes | Exact Supabase project HTTPS origin |
| `SUPABASE_JWT_AUDIENCE` | Backend-only configuration | Yes | `authenticated` |
| `GITHUB_TOKEN` | Backend-only secret | Optional | Fine-grained/read-only token for higher API limits |
| `ANALYSIS_VERSION` | Backend-only configuration | Yes | Increment only when analysis rules change |
| `DATABASE_POOL_SIZE` | Backend-only configuration | Optional | `5` |
| `DATABASE_MAX_OVERFLOW` | Backend-only configuration | Optional | `5` |
| `DATABASE_POOL_TIMEOUT_SECONDS` | Backend-only configuration | Optional | `10` |
| `DATABASE_POOL_RECYCLE_SECONDS` | Backend-only configuration | Optional | `300` |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Backend-only configuration | Optional | `10` |
| `AUTH_JWKS_TIMEOUT_SECONDS` | Backend-only configuration | Optional | `5` |
| `GITHUB_REQUEST_TIMEOUT_SECONDS` | Backend-only configuration | Optional | `15` |
| `FREE_ANONYMOUS_ANALYSIS_LIMIT` | Backend-only configuration | Optional | `5` |
| `FREE_AUTHENTICATED_ANALYSIS_LIMIT` | Backend-only configuration | Optional | `50` |
| `MAX_REQUEST_BODY_BYTES` | Backend-only configuration | Optional | `24576` |
| `MAX_REPOSITORY_FILES` | Backend-only configuration | Optional | `10000` |
| `MAX_REPOSITORY_BYTES` | Backend-only configuration | Optional | `104857600` |
| `MAX_REPOSITORY_PATH_BYTES` | Backend-only configuration | Optional | `1024` |
| `MAX_EVIDENCE_FILES` | Backend-only configuration | Optional | `40` |
| `MAX_EVIDENCE_FILE_BYTES` | Backend-only configuration | Optional | `262144` |
| `MAX_EVIDENCE_TOTAL_BYTES` | Backend-only configuration | Optional | `2097152` |
| `ANALYTICS_ENDPOINT` | Backend-only configuration | Optional | HTTPS provider ingestion URL |
| `ANALYTICS_WRITE_KEY` | Backend-only secret | Required with analytics endpoint | Provider key |
| `STRIPE_SECRET_KEY` | Backend-only secret | Required for billing | Stripe restricted secret key |
| `STRIPE_WEBHOOK_SECRET` | Backend-only secret | Required for billing | Stripe endpoint signing secret |
| `STRIPE_PRO_PRICE_ID` | Backend-only configuration | Required for billing | Hosted Pro recurring price ID |
| `STRIPE_PORTAL_RETURN_URL` | Backend-only configuration | Optional until billing | Exact frontend account URL |
| `ADMIN_USER_IDS` | Backend-only configuration | Optional | Comma-separated Supabase user IDs |
| `API_KEY_PEPPER` | Backend-only secret | Yes | At least 32 random characters |
| `GITHUB_APP_ID` | Backend-only configuration | Required for private-repo pilot | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | Backend-only secret | Required with App ID | PEM private key |

`DATABASE_URL`, `GITHUB_TOKEN`, and any future credentials must be entered as Render secrets. The
checked-in Blueprint intentionally contains names and safe defaults only.

### Vercel frontend

| Variable | Classification | Required | Value |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Public frontend | Yes | Exact Render HTTPS origin, no trailing path |
| `NEXT_PUBLIC_SUPABASE_URL` | Public frontend | Yes for auth | Exact Supabase project HTTPS origin |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public frontend | Yes for auth | Supabase anon/publishable key |
| `NEXT_PUBLIC_SITE_URL` | Public frontend | Yes | Exact canonical Vercel HTTPS origin |

Only `NEXT_PUBLIC_*` variables are referenced by frontend source. Never add `DATABASE_URL`,
`GITHUB_TOKEN`, a service-role key, or any backend token to Vercel.

## Staging smoke-test record

After both services are deployed, record pass/fail for HTTPS liveness and readiness, `/analyze`, a
successful small public GitHub analysis, provider error/partial behavior, sign-up/login/logout,
private history, machine compatibility, cache reuse, and a logged-out public share page. Repeat the
critical flow at desktop and mobile widths. Inspect browser network responses for mixed content,
stack traces, tokens, database details, raw repository evidence, and unexpected cookies.

The deployed URLs must be copied from the provider after successful deployment. Never substitute
example or predicted hostnames in a completion report.

The API exposes `/api/v1/health/live` for process liveness and `/api/v1/health/ready` for a real
database `SELECT 1` readiness check. Production uses pre-ping, bounded overflow, connection wait,
connect timeout, and connection recycling. Migration processes use a one-shot non-pooled
connection.

## Backup and restore

Enable managed daily backups and point-in-time recovery when the selected database plan supports
them. Before a schema migration, confirm a recent restorable backup. Test restoration into a
separate staging project; never test restores over production. Keep database credentials and
backup artifacts out of Git and application logs.

Rollback application code independently from schema. Run Alembic downgrade only for migrations
whose downgrade has been explicitly tested and whose data-loss implications are acceptable.

Supabase Auth and private history are live-verified in staging. The API validates token issuer,
audience, signature, expiry, and subject against
Supabase's rotating public keys; it does not receive passwords. Private repository access, billing,
and arbitrary repository execution are not part of this boundary. Future execution requires a
separate threat-modeled sandbox service; the API host must never execute repository commands or
expose a Docker socket.

## CI/CD controls

GitHub Actions runs independent backend and frontend verification with dependency caches and
cancels superseded runs. Pull-request jobs receive no production secrets. The staging workflow can
use the protected `RENDER_STAGING_DEPLOY_HOOK` environment secret only after successful `main`
verification. Vercel uses its protected Git integration. Production is a separate manually
dispatched, environment-approved gate and does not automatically reuse staging credentials.
