# Deployment

Deployment has not been performed. The following steps require user-provided infrastructure and
credentials.

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

Supabase Auth and private history are code complete but require a real project before live
verification. The API validates token issuer, audience, signature, expiry, and subject against
Supabase's rotating public keys; it does not receive passwords. Private repository access, billing,
and arbitrary repository execution are not part of this boundary. Future execution requires a
separate threat-modeled sandbox service; the API host must never execute repository commands or
expose a Docker socket.
