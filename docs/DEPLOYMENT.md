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

Supabase Auth, private repository access, billing, and arbitrary repository execution are not part
of the deployed MVP boundary. Future execution requires a separate threat-modeled sandbox service;
the API host must never execute repository commands or expose a Docker socket.
