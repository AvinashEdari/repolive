# Project state

Last updated: 2026-08-12

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
- Verification: 106 backend tests, 9 frontend interaction tests, migration upgrade/downgrade,
  Python lint and strict typing, frontend lint and typing, and the Next.js production build.
- Live `pypa/sampleproject` smoke test verified commit SHA retrieval, bounded analysis, setup
  guidance, cache reuse, and exclusion of raw evidence content.
- The staging frontend is live at `https://repolive-web.vercel.app`; the staging API is live at
  `https://repolive-api.onrender.com` and uses Supabase PostgreSQL and Supabase Auth.
- Staging validation confirmed HTTPS liveness/readiness, Alembic startup migration, PostgreSQL
  connectivity, exact-origin credentialed CORS, secure cookies, bounded public analysis, cache
  reuse, public sharing, machine compatibility, invalid-login handling, login, logout, authenticated
  persistence, private history, and cross-user history isolation.
- Desktop and mobile viewport checks found no horizontal overflow on the analysis workspace.
- Stage 5 hardening bounds actual request bodies, repository paths, and encoded evidence before
  decoding; normalizes anonymous cookies and public IDs; disables production API documentation;
  adds provider retry guidance, HSTS, and permissions policy headers; and applies atomic anonymous
  and authenticated new-analysis allowances while keeping cached results reusable.
- Security reporting, privacy/retention boundaries, and a production hardening checklist are
  documented. Security regression coverage is included in the 89-test backend suite.
- Stage 6 adds secret-safe GitHub Actions verification and gated deployment workflows, structured
  request/analysis observability, canonical and social metadata, robots and sitemap routes, public
  analysis metadata, draft Privacy/Terms/Security/Acceptable Use/Contact pages, and testing,
  troubleshooting, backup/restore, rollback, and incident runbooks.
- Stage 7 adds bounded deterministic pasted-error diagnosis with repository context, comparison of
  two cached public analyses, one-call official GitHub discovery with transparent multi-signal
  ranking, and an explicit-consent architecture for a future local compatibility client. No local
  machine inspection, billing, sandbox, or repository execution was added.
- Operational follow-up adds dry-run-first 90-day cleanup for expired counters and unowned reports,
  bounded README setup-section extraction, and conflicting Node.js lockfile warnings.

## Planned

- Private repository authorization.
- Version-resolution conflict analysis beyond multiple Node.js lockfile detection.

## Known constraints

- Docker CLI is installed but its daemon was not running during discovery.
- GitHub authentication is optional; unauthenticated API rate limits apply when `GITHUB_TOKEN`
  is unset.
- Historical virtual environments reference removed Python installations. Verification uses the
  ignored `.venv-verify` Python 3.11 environment; environments are not committed.
- Legacy landing-page source files are owned by an inaccessible prior sandbox identity. The new
  results workspace was added as `/analyze`; linking it from `/` remains blocked by that ACL.
- Supabase PostgreSQL, Supabase Auth, Render, and Vercel are configured and verified for staging.
- Cookie quotas deter ordinary anonymous overuse but require distributed IP/risk controls for
  production abuse resistance.
