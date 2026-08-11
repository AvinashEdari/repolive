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
