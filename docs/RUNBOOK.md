# Operations runbook

## Service map

- Web: Vercel, `https://repolive-web.vercel.app`
- API: Render, `https://repolive-api.onrender.com`
- Database and authentication: Supabase PostgreSQL and Supabase Auth
- Source and verification: GitHub and GitHub Actions

## Triage order

1. Check Vercel, Render, Supabase, and GitHub status pages.
2. Check API `/api/v1/health/live`; then `/api/v1/health/ready` for database readiness.
3. Correlate safe JSON logs by `request_id`. Use `analysis_id` for completed reports.
4. Classify failures as frontend, API, database, authentication, GitHub provider, or quota.
5. Do not paste tokens, cookies, request bodies, database URLs, or repository evidence into tickets.

## Backup and restore

Enable Supabase backups appropriate to the paid plan before production. Record the schedule,
retention, encryption, and restore owner. Test restores only into an isolated project. After restore,
run Alembic to `head`, verify readiness, compare expected row counts without exposing report data,
then smoke-test ownership and sharing before routing traffic.

## Retention maintenance

From the backend service directory, preview the 90-day policy with
`python -m app.maintenance --days 90`. Record the reported counts, take or confirm a current backup,
then run `python -m app.maintenance --days 90 --execute` during an approved maintenance window.
Verify readiness and a known owned report afterward. The command deletes expired usage counters and
only cached reports without any current user-history owner.

## Rollback

For frontend regressions, promote the last verified Vercel deployment. For API regressions, deploy
the last verified Render commit. Prefer a forward database fix: application rollback is safe only
when the older code supports the current schema. If a schema downgrade is unavoidable, stop writes,
take and verify a backup, test the downgrade in isolation, obtain explicit approval, downgrade one
revision, and immediately re-run readiness and ownership checks.

## Incident handling

For suspected credential exposure, restrict access, rotate the credential at its provider, deploy
the replacement, invalidate affected sessions when applicable, and review sanitized audit logs.
For abuse, preserve safe aggregate evidence, apply edge controls, and avoid identifying users from
untrusted forwarding headers. Document timeline, impact, remediation, and follow-up tests.
