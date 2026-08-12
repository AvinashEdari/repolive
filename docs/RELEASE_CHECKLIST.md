# RepoLive release checklist

## Automated and product gate

- [ ] Backend tests, security tests, Ruff, format, strict mypy, and migrations pass.
- [ ] Frontend tests, ESLint, TypeScript, build, and npm audit pass.
- [ ] CI succeeds before Render/Vercel deployment.
- [ ] Public analysis, cache, sharing, history, quota, compatibility, diagnosis, comparison, and
      discovery pass in production at desktop, tablet, and mobile sizes.
- [ ] Analytics is disabled or verified to send only allowlisted categorical properties.
- [ ] Admin denies non-admins; API keys are one-time-visible, hashed, revocable, and bounded.

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
