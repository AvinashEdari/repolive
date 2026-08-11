# Production hardening checklist

## Application

- [ ] Run with `APP_ENV=production`; confirm API docs and debug tracebacks are unavailable.
- [ ] Use exact HTTPS `WEB_ORIGIN` and explicit `ALLOWED_HOSTS`; reject wildcard configuration.
- [ ] Keep request, repository-tree, repository-byte, path, evidence-file, evidence-total, and
      provider-timeout limits enabled.
- [ ] Verify repository commands remain display-only and raw evidence fields remain excluded.
- [ ] Run security regression tests, lint, strict typing, frontend tests/build, dependency audit,
      and migration upgrade/downgrade checks for every release.

## Edge and abuse controls

- [ ] Configure distributed per-IP/per-network rate limiting at the CDN or API gateway.
- [ ] Add bot/risk rules for cookie rotation, account farms, high-cardinality repository probes,
      and repeated provider failures.
- [ ] Preserve RepoLive's anonymous-session and authenticated-user new-analysis allowances.
- [ ] Allow cache reuse without consuming a new-analysis allowance, while still applying edge
      request-rate limits.
- [ ] Monitor GitHub rate-limit headers and alert before shared provider capacity is exhausted.

## Secrets and logging

- [ ] Store database and GitHub credentials only in the backend provider's secret store.
- [ ] Confirm Vercel exposes only documented `NEXT_PUBLIC_*` Supabase/public API values.
- [ ] Redact Authorization, Cookie, Set-Cookie, database URLs, and provider tokens in logs and APM.
- [ ] Enable provider audit logs and document credential-rotation ownership.

## Data lifecycle

- [ ] Publish concrete retention periods for cached reports, counters, logs, test accounts, and
      backups; automate deletion where promised.
- [ ] Test history-link deletion, subject erasure, account deletion, and backup expiry.
- [ ] Explain that share links are public and ensure public reports contain no account identifier.
- [ ] Review every new analytics, monitoring, or AI provider before sending it user or repository
      data.

## Infrastructure

- [ ] Enforce HTTPS, HSTS, secure cookies, supported TLS versions, database TLS, and backups.
- [ ] Restrict database network access and privileges; test restore in an isolated staging project.
- [ ] Configure WAF/request limits, availability alerts, database saturation alerts, and dependency
      vulnerability monitoring.
- [ ] Re-run safe external smoke tests for CORS, headers, authentication, ownership, quota behavior,
      error redaction, and public sharing after deployment.
