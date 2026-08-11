# Project state

Last updated: 2026-08-11

## Implemented and verified

- Git repository initialized on `main` at `D:\repolive`.
- Next.js product shell with a real API-backed repository URL form.
- FastAPI health and analysis routes, provider abstraction, and strict GitHub URL parsing.
- Bounded GitHub API ingestion for public repository metadata and recursive file trees, with
  explicit not-found, rate-limit, truncation, file-count, and known-byte limit failures.
- Composable deterministic pipeline for language distribution, important files, technology
  markers, and evidence-backed project types.
- Bounded allowlisted evidence-file hydration by Git blob ID; raw contents are never returned.
- Dependency parsing for npm and Python, runtime constraints, dependency-backed frameworks,
  documentation/test/CI/container signals, and explainable documentation/readiness scores.
- Responsive real-results workspace at `/analyze`.
- Durable local SQLite storage, random public analysis IDs, shareable API/web routes, and a
  configurable transactional anonymous allowance using an HTTP-only cookie.
- Direct dependency parsing expanded to Cargo, Go modules, Maven, Gradle, RubyGems, Composer,
  and NuGet, including defensive malformed-manifest behavior.
- Evidence-derived purpose, setup steps, prerequisites, compatibility conditions, strengths,
  risks, missing essentials, and explicit unknowns are shown in the results workspace.
- Commit-SHA and analysis-version cache reuse, normalized persistence fields, Alembic migrations,
  and installed PostgreSQL/Supabase driver boundary.
- Typed provider failures, partial evidence warnings, security headers, trusted hosts, request
  size/time limits, strict production configuration, and a disabled explanation-provider path.
- PostgreSQL staging readiness includes bounded/pre-ping connection pooling, connect/wait/recycle
  timeouts, database readiness probes, a Render blueprint, and explicit backup/restore guidance.
- Supabase account UI, server-side access-token verification, anonymous or authenticated analysis,
  cache-state reporting, and authorization-scoped saved history are implemented.
- Alembic-managed user-to-analysis links support private listing and removal without exposing
  account data through stable public reports.
- Users can compare explicitly supplied OS, architecture, runtime versions, and Docker availability
  with repository evidence. Results are compatible, probably compatible, incompatible, or unknown;
  absent hardware requirements are never guessed.
- Responsive SaaS presentation now uses consistent navigation, accessible account controls,
  progressive report sections, expandable score/dependency evidence, explicit partial/cache states,
  display-only command warnings, and a guided machine-compatibility form.
- Supabase JWT claims are regression-tested with locally signed asymmetric tokens. Authenticated
  requests no longer consume anonymous allowance, and PostgreSQL/SQLite history linking uses an
  atomic conflict-safe insert.
- Production configuration accepts only the supported PostgreSQL driver and exact HTTPS web and
  Supabase origins. Migration tests verify keys, cache uniqueness, ownership indexes, cascade
  behavior, downgrade, and offline PostgreSQL DDL generation.
- The Render Blueprint now declares the full production pool, authentication, request, evidence,
  and quota configuration. Deployment documentation defines exact Supabase, Render, and Vercel
  variable boundaries and staging smoke-test requirements.
- Verification: 78 backend tests, 6 frontend interaction tests, migration upgrade/downgrade,
  Python lint and strict typing, frontend lint and typing, and the Next.js production build.
- Live `pypa/sampleproject` smoke test verified commit SHA retrieval, bounded analysis, setup
  guidance, cache reuse, and exclusion of raw evidence content.

## Planned

- Live Supabase/PostgreSQL staging authentication and persistence verification.
- Private repository authorization.
- Broader lockfile/version-conflict analysis and README setup-section extraction.

## Known constraints

- Docker CLI is installed but its daemon was not running during discovery.
- GitHub authentication is optional; unauthenticated API rate limits apply when `GITHUB_TOKEN`
  is unset.
- Historical virtual environments reference removed Python installations. Verification uses the
  ignored `.venv-verify` Python 3.11 environment; environments are not committed.
- Legacy landing-page source files are owned by an inaccessible prior sandbox identity. The new
  results workspace was added as `/analyze`; linking it from `/` remains blocked by that ACL.
- SQLite and migrations are verified locally. The PostgreSQL driver and migration path are
  implemented, but no live Supabase database has been configured or deployed.
- Vercel, Render, and Supabase deployment configuration is prepared, but this workspace has no
  authenticated provider CLI or dashboard session; no staging URL has been created or claimed.
- Cookie quotas deter ordinary anonymous overuse but require distributed IP/risk controls for
  production abuse resistance.
