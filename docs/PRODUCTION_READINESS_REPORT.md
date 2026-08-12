# RepoLive production readiness report

Last updated: 2026-08-12

## Decision

The public-repository staging product is code-complete and suitable for controlled staging use.
A public paid launch and private-repository launch are **not approved yet** because Stripe, the
GitHub App, distributed edge protection, external monitoring, backup/restore drills, and
professional legal review still require real external configuration and verification.

Launch classification:

- Controlled public-repository staging: **READY AND VERIFIED**.
- Public free production: **NOT YET APPROVED** pending distributed abuse controls, monitoring,
  scheduled retention, restore drill, and final production-domain validation.
- Paid production: **NOT READY**; Stripe is intentionally unconfigured in staging.
- Private-repository production: **NOT READY**; the GitHub App integration remains disabled until
  live authorization and isolation testing is complete.

Arbitrary repository execution remains disabled. RepoLive does not clone repositories, run
repository commands, or install repository dependencies.

## Verified platform

- Frontend: responsive Next.js application deployed on Vercel staging.
- Backend: FastAPI service deployed on Render staging with bounded GitHub API access.
- Database and auth: Supabase PostgreSQL and Supabase Auth staging integration.
- Product: public analysis, deterministic reports, cache reuse, public sharing, private account
  history, machine compatibility, error diagnosis, comparison, and discovery.
- Security: exact-origin CORS, trusted hosts, HTTPS, secure production configuration, bounded input
  and evidence, authorization-scoped history, safe serialization, and secret-safe logs.
- Operations: gated CI/CD, health/readiness endpoints, structured request IDs, rollback and incident
  procedures, privacy/retention boundaries, and draft legal pages.

## Final resolution verification

- 131 backend tests pass, including security, authorization, quota, billing, retention, and
  fail-closed visibility regressions.
- Ruff lint, Ruff formatting, and strict mypy pass.
- Alembic upgrades through `0005_analysis_visibility`, downgrades to base, and upgrades back to head
  on a disposable database.
- 12 frontend interaction tests, ESLint, TypeScript, and the Next.js production build pass.
- `npm audit --audit-level=high` reports zero vulnerabilities.
- Live staging readiness reports PostgreSQL `ok`; public GitHub analysis, commit-SHA cache reuse,
  public sharing, compatibility, deterministic diagnosis, comparison, and discovery succeed.
- Exact-origin CORS succeeds for the Vercel origin and is absent for a hostile origin. HSTS,
  clickjacking protection, MIME sniffing protection, unauthenticated history/admin denial, API
  `no-store`, and absence of raw evidence in responses were verified.
- Billing status truthfully reports Stripe as unconfigured. No paid or private-repository capability
  is represented as live.

The final code resolution was pushed on `main` as `65cdff9`; this report is maintained in the
subsequent documentation commit recorded by Git history.

## Stage 8 architecture

- Analytics is optional and allowlisted; repository identifiers, contents, tokens, and user secrets
  are excluded from event payloads.
- Free and Pro rules are centralized in an entitlement service rather than analyzer code.
- Billing uses Stripe-hosted Checkout and Portal URLs, signed webhooks, event idempotency, and
  subscription-state synchronization. Raw card data never enters RepoLive.
- External API keys are shown once, HMAC-hashed at rest, revocable, and quota-bound. External report
  responses contain derived report data and never hydrated raw evidence.
- Admin aggregates require an explicit backend-only administrator user ID allowlist.
- Organization, membership, role, and shared-analysis tables establish the team boundary; invites,
  quota sharing, and member-management UI intentionally remain future work.
- GitHub App scaffolding verifies installation access and creates short-lived installation tokens in
  memory. Persistence and public lookups now fail closed on explicit visibility, but private
  analysis remains disabled until owner-scoped ingestion and live isolation are verified end to end.

## Supported ecosystems

Deterministic analysis covers JavaScript/TypeScript, Python, Rust, Go, Java/Maven/Gradle, Ruby,
PHP/Composer, and .NET/NuGet evidence, plus documentation, tests, CI, containers, runtimes,
important files, setup guidance, and explainable health signals. Results remain evidence-limited
and explicitly report unknowns.

## Launch blockers

1. Configure and test Stripe products, prices, webhook, portal, cancellations, failed payments,
   refunds/support policy, taxes, and downgrade behavior.
2. Configure a least-privilege GitHub App and verify private-by-default persistence, access removal,
   organization authorization, token expiry, and cross-user isolation.
3. Add distributed edge/IP/risk controls; application quotas alone are not distributed protection.
4. Select external monitoring and alerts, schedule retention cleanup, and complete restore drills.
5. Obtain professional review of Privacy, Terms, Acceptable Use, billing, and retention language.
6. Complete the production checklist at desktop, tablet, and mobile sizes after all production
   credentials and domains are final.

The authoritative gate is [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Production URLs and final
commit identity must only be recorded after deployment and direct verification.
