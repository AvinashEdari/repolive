# Architecture

RepoLive is a modular monolith: a Next.js application consumes a FastAPI API backed by
SQLAlchemy. Provider-neutral repository contracts isolate GitHub-specific retrieval. Composable
deterministic analyzers consume an immutable bounded snapshot and emit typed findings with paths.

The request flow is URL validation, provider metadata/tree/allowlisted-blob retrieval,
deterministic analysis, commit/version cache lookup, quota accounting, persistence, and response.
SQLite is used locally; the same SQLAlchemy boundary and Alembic migrations support PostgreSQL.

Raw evidence text is internal and excluded from serialization. Repository code is never cloned,
imported, installed, built, or executed. Optional explanation providers receive structured
findings only and are disabled by default.

Every API request receives a bounded request ID and emits a structured JSON completion event with
method, route, status, and duration. Analysis completion events include the random public analysis
ID, cache state, authentication state, provider, and file count. Provider, database, authentication,
and quota failures use safe categorical fields. Logs exclude headers, cookies, tokens, database
URLs, raw bodies, and repository evidence. A small provider-neutral error-monitor interface allows
optional external reporting without making request handling depend on it.

GitHub Actions separates backend and frontend verification. Staging deployment is triggered only
after successful verification on `main`; production remains an explicitly approved environment.
