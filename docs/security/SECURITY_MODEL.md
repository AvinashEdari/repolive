# Security model

Repository URLs and content are untrusted. Retrieval must enforce allowlisted hosts, safe redirects, byte/file/time limits, escaped output, and token-safe logging. Repository commands never run on the API host. Execution belongs in a separately isolated service after threat modelling.

The preview proof of concept implements a separate worker/runtime boundary for approved root-level
static HTML, locked Node web applications, and requirements-locked Python web applications. It
remains disabled by default. Docker is a development adapter, not a hostile multi-tenant security
claim. See `PREVIEW_THREAT_MODEL.md`; production requires stronger isolation and network policy.

Allowlisted evidence files are retrieved by Git object ID with strict count and byte limits.
Malformed base64 is rejected and non-UTF-8 evidence is skipped. Raw evidence content is excluded
from API serialization to avoid reflecting repository-controlled text or environment examples.

Supabase passwords are handled only by Supabase. The browser persists and refreshes the Supabase
session using the public anon configuration; access tokens are sent as Bearer credentials only to
the RepoLive API. The API validates the rotating public-key signature, exact issuer and audience,
expiry, issued-at time, and subject. It stores only the user subject on private history links.
Tokens, database URLs, and service-role credentials must never be logged or exposed to the browser.
History listing and removal are always scoped by the verified subject; public reports contain no
account identifier.

Public analysis identifiers are generated from cryptographically secure random bytes and looked
up with parameterized SQLAlchemy statements. Anonymous identifiers are random HTTP-only,
SameSite=Lax cookies and are marked Secure in production. Cookie clearing can bypass this MVP
allowance, so production abuse protection still requires IP/risk-based rate limiting. Anonymous
session and authenticated-user counters are updated atomically and charge only newly persisted
analyses; deterministic cache reuse does not consume another new-analysis allowance. Infrastructure
may add IP/network/device-risk enforcement outside this boundary, but the application does not trust
client-supplied forwarding headers as identity.

The API uses explicit trusted hosts and CORS origins, rejects oversized declared request bodies,
maps provider failure classes without leaking credentials, and returns nosniff, frame-denial,
referrer, CSP, and cache-control headers. GitHub retrieval uses an official fixed API host,
per-request timeouts, bounded request counts, strict response-shape validation, and skips symlinks
and submodules. Missing, non-UTF-8, or oversized evidence becomes a partial-analysis warning.
Actual streamed request bodies are also bounded. Repository paths reject traversal components,
control characters, absolute paths, and excessive byte length. Encoded blob size is checked before
base64 decoding. Production disables interactive API documentation and adds HSTS and a restrictive
permissions policy.
