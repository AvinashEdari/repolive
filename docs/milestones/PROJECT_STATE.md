# Project state

Last updated: 2026-08-10

## Implemented and verified

- Git repository initialized on `main` at `D:\repolive`.
- Next.js product shell with a real API-backed repository URL form.
- FastAPI health and analysis routes, provider abstraction, and strict GitHub URL parsing.
- Bounded GitHub API ingestion for public repository metadata and recursive file trees, with
  explicit not-found, rate-limit, truncation, file-count, and known-byte limit failures.
- Verification: 13 backend tests, Python lint and strict typing, frontend lint and typing,
  and the Next.js production build.

## Planned

- Deterministic analyzers, persistence, shareable results, usage limits, authentication,
  compatibility, and setup guidance.

## Known constraints

- Docker CLI is installed but its daemon was not running during discovery.
- GitHub authentication is optional; unauthenticated API rate limits apply when `GITHUB_TOKEN`
  is unset.
- A stale `.venv` references a removed Python installation. Verification currently uses the
  ignored `.venv311` project environment; neither environment is committed.
