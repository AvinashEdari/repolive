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

## Migrations

Use a disposable database. Upgrade to head, downgrade to base, then upgrade a fresh database to
head. Never run downgrade testing against production. PostgreSQL DDL rendering and migration
structure are also covered by the backend test suite.

## External smoke test

Use a small public repository. Confirm liveness/readiness, exact-origin CORS, successful analysis,
cache reuse, absence of raw evidence, public sharing, authentication, private history ownership,
logout, safe errors, security headers, robots, sitemap, and legal routes. Do not load-test staging.
