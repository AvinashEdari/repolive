# Deployment

Deployment has not been performed. The following steps require user-provided infrastructure and
credentials.

1. Create a Supabase/PostgreSQL database and obtain its server-side connection URL.
2. Set `APP_ENV=production`, a `postgresql+psycopg://` `DATABASE_URL`, HTTPS `WEB_ORIGIN`, explicit
   `ALLOWED_HOSTS`, a new `ANALYSIS_VERSION`, and optionally a server-only `GITHUB_TOKEN`.
3. From `apps/api`, run `python -m alembic -c alembic.ini upgrade head` against that database.
4. Build and deploy the FastAPI service without exposing `.env` or repository tokens.
5. Set `NEXT_PUBLIC_API_URL` to the public HTTPS API URL, run `npm run build:web`, and deploy the
   Next.js application.
6. Add platform-level rate limiting, request logging with credential redaction, database backups,
   monitoring, TLS, and secret rotation before public launch.
7. Run backend/frontend suites and a public-repository smoke test in the deployed environment.

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

Supabase Auth, private repository access, billing, and arbitrary repository execution are not part
of the deployed MVP boundary. Future execution requires a separate threat-modeled sandbox service;
the API host must never execute repository commands or expose a Docker socket.
