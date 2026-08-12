# Troubleshooting

## Frontend cannot reach the API

Confirm `NEXT_PUBLIC_API_URL`, HTTPS, exact API hostname, and Render readiness. Verify CORS allows
the exact Vercel origin with credentials. Browser extensions or embedded browsers can block
`onrender.com`; reproduce in a normal supported browser before changing CORS.

## API is slow after inactivity

Render free instances can cold-start. Check liveness first and wait for readiness. Upgrade the
service tier for predictable production latency rather than increasing application timeouts.

## GitHub returns 429 or 403

Respect `Retry-After`. Check the provider rate-limit budget and optional backend-only GitHub token.
Do not expose the token to Vercel or browsers. Cached reports remain reusable without a new-analysis
charge.

## Authentication fails

Confirm the Supabase site URL and redirect allowlist, project URL, JWT audience, token expiry, and
API clock. Never log or paste the access token. A 401 should clear the client session and prompt a
new login.

## Readiness fails

Check Supabase availability, pool saturation, TLS, connection timeout, database credentials, and
whether Alembic reached `head`. Do not print `DATABASE_URL`. Test any credential rotation in staging.

## Migration fails

Stop repeated deploys, preserve logs without secrets, inspect the current Alembic revision, and test
the same transition on a restored isolated database. Prefer a forward corrective migration.

## Local generated-file permission errors

Stop active Next.js processes before rebuilding. Use the repository's existing generated-file
tracking policy for `next-env.d.ts`; do not blindly delete or commit unrelated generated output.
