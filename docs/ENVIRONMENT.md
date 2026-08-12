# Environment reference

Stage 8 optional server integrations use `ANALYTICS_ENDPOINT`, `ANALYTICS_WRITE_KEY`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRO_PRICE_ID`,
`STRIPE_PORTAL_RETURN_URL`, `ADMIN_USER_IDS`, `API_KEY_PEPPER`, `GITHUB_APP_ID`, and
`GITHUB_APP_PRIVATE_KEY`. `API_KEY_PEPPER` is required and must contain at least 32 random
characters in production. Stripe must be configured as a complete set or left disabled. None of
these values may use a `NEXT_PUBLIC_` prefix.

- `APP_ENV`: `development`, `test`, or `production`. Production activates strict validation.
- `DATABASE_URL`: server-only SQLAlchemy URL. SQLite is the local default; production accepts
  `postgresql://` or `postgresql+psycopg://` with the synchronous psycopg driver.
- `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`: bounded production connection-pool capacity.
- `DATABASE_POOL_TIMEOUT_SECONDS`: maximum wait for a pooled connection.
- `DATABASE_POOL_RECYCLE_SECONDS`: retires long-lived connections before provider idle limits.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`: database handshake timeout.
- `ANALYSIS_VERSION`: invalidates cached reports when deterministic rules change.
- `WEB_ORIGIN`: exact browser origin allowed by CORS; HTTPS is required in production.
- `ALLOWED_HOSTS`: comma-separated API hostnames; local/wildcard values are rejected in production.
- `GITHUB_TOKEN`: optional server-only token for higher GitHub API limits. Never expose it publicly.
- `SUPABASE_URL`: project URL used by the API to validate Supabase JWT issuer and public signing keys.
- `SUPABASE_JWT_AUDIENCE`: expected access-token audience; normally `authenticated`.
- `AUTH_JWKS_TIMEOUT_SECONDS`: bounded public signing-key lookup timeout.
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`: browser-safe Supabase Auth configuration. Never use a service-role key here.
- `GITHUB_REQUEST_TIMEOUT_SECONDS`: timeout applied to each GitHub API request.
- `FREE_ANONYMOUS_ANALYSIS_LIMIT`: successful new analyses allowed per anonymous cookie identity.
- `FREE_AUTHENTICATED_ANALYSIS_LIMIT`: successful new analyses allowed per verified user subject.
- `MAX_REQUEST_BODY_BYTES`: maximum actual API request body size.
- `MAX_REPOSITORY_FILES`, `MAX_REPOSITORY_BYTES`, `MAX_REPOSITORY_PATH_BYTES`: repository snapshot
  limits.
- `MAX_EVIDENCE_FILES`, `MAX_EVIDENCE_FILE_BYTES`, `MAX_EVIDENCE_TOTAL_BYTES`: allowlisted text limits.
- `NEXT_PUBLIC_API_URL`: browser-visible API base URL; it must never contain credentials.
- `NEXT_PUBLIC_SITE_URL`: canonical public frontend origin used for metadata, robots, and sitemap.

No AI environment variable is required. The explanation provider is disabled by default.

Use `.env.production.example` only as a variable-name reference. Replace every example hostname
and credential through the deployment platform's secret manager; never commit the populated file.
The API and migration process need `DATABASE_URL`, but the browser must never receive it. The
Supabase anon key is designed for browser use; a service-role key is not used anywhere in RepoLive.
