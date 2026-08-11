# Environment reference

- `APP_ENV`: `development`, `test`, or `production`. Production activates strict validation.
- `DATABASE_URL`: SQLAlchemy URL. SQLite is the local default; production requires PostgreSQL.
- `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`: bounded production connection-pool capacity.
- `DATABASE_POOL_TIMEOUT_SECONDS`: maximum wait for a pooled connection.
- `DATABASE_POOL_RECYCLE_SECONDS`: retires long-lived connections before provider idle limits.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`: database handshake timeout.
- `ANALYSIS_VERSION`: invalidates cached reports when deterministic rules change.
- `WEB_ORIGIN`: exact browser origin allowed by CORS; HTTPS is required in production.
- `ALLOWED_HOSTS`: comma-separated API hostnames; local/wildcard values are rejected in production.
- `GITHUB_TOKEN`: optional server-only token for higher GitHub API limits. Never expose it publicly.
- `GITHUB_REQUEST_TIMEOUT_SECONDS`: timeout applied to each GitHub API request.
- `FREE_ANONYMOUS_ANALYSIS_LIMIT`: successful new analyses allowed per anonymous cookie identity.
- `MAX_REPOSITORY_FILES`, `MAX_REPOSITORY_BYTES`: repository snapshot limits.
- `MAX_EVIDENCE_FILES`, `MAX_EVIDENCE_FILE_BYTES`, `MAX_EVIDENCE_TOTAL_BYTES`: allowlisted text limits.
- `NEXT_PUBLIC_API_URL`: browser-visible API base URL; it must never contain credentials.

No AI environment variable is required. The explanation provider is disabled by default.

Use `.env.production.example` only as a variable-name reference. Replace every example hostname
and credential through the deployment platform's secret manager; never commit the populated file.
