# Security model

Repository URLs and content are untrusted. Retrieval must enforce allowlisted hosts, safe redirects, byte/file/time limits, escaped output, and token-safe logging. Repository commands never run on the API host. Execution belongs in a separately isolated service after threat modelling.

Allowlisted evidence files are retrieved by Git object ID with strict count and byte limits.
Malformed base64 is rejected and non-UTF-8 evidence is skipped. Raw evidence content is excluded
from API serialization to avoid reflecting repository-controlled text or environment examples.

Public analysis identifiers are generated from cryptographically secure random bytes and looked
up with parameterized SQLAlchemy statements. Anonymous identifiers are random HTTP-only,
SameSite=Lax cookies and are marked Secure in production. Cookie clearing can bypass this MVP
allowance, so production abuse protection still requires IP/risk-based rate limiting.

The API uses explicit trusted hosts and CORS origins, rejects oversized declared request bodies,
maps provider failure classes without leaking credentials, and returns nosniff, frame-denial,
referrer, CSP, and cache-control headers. GitHub retrieval uses an official fixed API host,
per-request timeouts, bounded request counts, strict response-shape validation, and skips symlinks
and submodules. Missing, non-UTF-8, or oversized evidence becomes a partial-analysis warning.
