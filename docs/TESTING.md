# Testing

## Backend

From the repository root with the development dependencies installed:

```powershell
.venv-local\Scripts\python -m pytest apps/api/tests -q
.venv-local\Scripts\python -m ruff check --no-cache apps/api
.venv-local\Scripts\python -m ruff format --check --no-cache apps/api
.venv-local\Scripts\python -m mypy apps/api/app
```

The suite covers validation, hostile provider responses, parsers, authentication, authorization,
quotas, persistence, compatibility, security headers, production startup, and migrations.

## Frontend

```powershell
npm.cmd run check
npm.cmd run build:web
npm.cmd audit --audit-level=high
```

`check` runs ESLint, TypeScript, and Vitest. The production build is a separate mandatory gate.

## Preview verification

`pytest apps/api/tests/test_previews.py` covers policy, trusted profiles, lifecycle transitions,
ownership/concurrency and log sanitization. `python -m app.previews.reconcile` is a dry run;
`--execute` removes only exact labeled resources. Worker, queue, router, cleanup and harmless
resource/network adversarial tests must run only on a dedicated local or staging host, never shared
production infrastructure.

With an explicitly approved local Docker engine, run
`$env:RUN_PREVIEW_DOCKER_TESTS='1'; python -m pytest tests/test_preview_docker_integration.py` from
`apps/api`. It clones a pinned public commit, verifies non-root/read-only/capability/PID/network and
mount controls, serves through the opaque router, stops it, and verifies destruction.

## Migrations

Use a disposable database. Upgrade to head, downgrade to base, then upgrade a fresh database to
head. Never run downgrade testing against production. PostgreSQL DDL rendering and migration
structure are also covered by the backend test suite.

## External smoke test

Use a small public repository. Confirm liveness/readiness, exact-origin CORS, successful analysis,
cache reuse, absence of raw evidence, public sharing, authentication, private history ownership,
logout, safe errors, security headers, robots, sitemap, and legal routes. Do not load-test staging.
