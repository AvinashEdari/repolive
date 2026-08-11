# Security policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, access tokens, private account
data, or database contents. Contact the repository owner privately through GitHub and include the
affected version, reproduction steps, impact, and the smallest safe proof of concept. Do not access
other users' data, degrade the staging service, or run high-volume tests.

## Supported boundary

RepoLive analyzes public GitHub repositories without cloning or executing them. Repository paths,
metadata, manifests, README text, CI files, Docker files, dependency declarations, and commands are
hostile input. RepoLive never runs repository commands, installs dependencies, follows URLs found in
repository content, or returns raw hydrated evidence.

GitHub access is restricted to HTTPS requests to the fixed official API origin. Supabase access
tokens are verified by issuer, audience, signature, expiry, issued-at time, and subject. Database
queries use SQLAlchemy parameters. Browser rendering relies on React escaping and does not inject
repository HTML.

## Operational requirements

- Keep GitHub tokens, database URLs, and any Supabase server credentials backend-only.
- Require TLS verification; never add an insecure transport exception.
- Configure exact CORS origins and trusted hostnames without wildcards.
- Apply migrations before starting application traffic.
- Put distributed IP/risk rate limiting and monitoring in front of the API.
- Redact authorization, cookie, database, and provider-token values from platform logs.
- Rotate a credential immediately if it appears in a log, response, build artifact, or commit.

See [the security model](docs/security/SECURITY_MODEL.md),
[privacy and retention](docs/security/PRIVACY_AND_RETENTION.md), and the
[production hardening checklist](docs/security/PRODUCTION_HARDENING_CHECKLIST.md).
