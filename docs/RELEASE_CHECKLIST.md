# RepoLive release checklist

## Automated and product gate

- [x] Backend tests, security tests, Ruff, format, strict mypy, and migrations pass.
- [x] Frontend tests, ESLint, TypeScript, build, and npm audit pass.
- [x] CI succeeds before Render/Vercel deployment.
- [x] Public analysis, cache, sharing, compatibility, diagnosis, comparison, and discovery pass on
      staging; history, ownership, quota, and responsive behavior have automated regression coverage.
- [x] Analytics is disabled by default and permits only allowlisted categorical properties.
- [x] Admin denies non-admins; API keys are one-time-visible, hashed, revocable, and bounded.

## Commercial, private repository, and operations gate

- [ ] Stripe live product/price, signed webhook, portal, tax, cancellation, failed-payment, duplicate
      event, downgrade, refund/support policy, and professional legal review are complete.
- [ ] GitHub App has Metadata/Contents read only; user/org ownership, token expiry, access removal,
      private-by-default reports, and cross-user isolation are verified.
- [ ] Paid always-on backend capacity, distributed edge limits, monitoring/alerts, backups/restores,
      and scheduled retention are configured.
- [ ] HTTPS, headers, mixed content, secret leakage, logs, rollback owners, and known-good releases
      receive final review.

Unchecked external gates block a public paid launch even when application code is complete.

Current decision: controlled public-repository staging is approved. Public free production, paid
production, and private-repository production remain blocked by the unchecked operational gates.

## Isolated preview gate

- [x] Feature defaults off; control/execution separation, exact-SHA static policy, ownership,
      quotas, lifecycle and sanitized events are implemented.
- [ ] Hardened provider, durable distributed queue and isolated registrable TLS domain are live.
- [ ] Provider egress blocks metadata, private, control-plane and cross-preview networks.
- [ ] Expiry scheduler, monitoring, cost controls, reconciliation and adversarial tests pass.

Until every unchecked item passes, previews are local-development-only.

## Isolated preview gate

- [x] Feature defaults off; control/execution separation, exact-SHA static policy, ownership,
      quotas, lifecycle and sanitized events are implemented.
- [ ] Hardened provider, durable distributed queue and isolated registrable TLS domain are live.
- [ ] Provider egress blocks metadata, private, control-plane and cross-preview networks.
- [ ] Expiry scheduler, monitoring, cost controls, reconciliation and adversarial tests pass.

Until every unchecked item passes, previews are local-development-only.
