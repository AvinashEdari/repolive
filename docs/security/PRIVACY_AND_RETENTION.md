# Privacy and data retention

Preview records retain repository identity, immutable commit, user subject, lifecycle timestamps,
bounded sanitized events and aggregate usage. They never retain credentials, arbitrary environment
variables, raw logs or repository contents. Sandbox storage must be destroyed at stop/expiry. A
production retention scheduler for old preview events and usage is still external and unconfigured.

Preview records retain repository identity, immutable commit, user subject, lifecycle timestamps,
bounded sanitized events and aggregate usage. They never retain credentials, arbitrary environment
variables, raw logs or repository contents. Sandbox storage must be destroyed at stop/expiry. A
production retention scheduler for old preview events and usage is still external and unconfigured.

## Data stored

RepoLive stores deterministic reports for public repositories: normalized repository identity,
commit SHA, bounded file paths and sizes, public GitHub metadata, derived findings, scores, setup
guidance, creation time, and a random public report ID. It stores anonymous usage identifiers and
counters. For signed-in users it stores the Supabase subject only in private history links and an
account-level new-analysis counter.

## Data not stored

RepoLive does not store passwords, Supabase access tokens, GitHub tokens, service-role credentials,
database credentials, raw manifest/README/CI/Docker contents, repository source code, machine
profile submissions, or arbitrary URLs found inside repositories. The API does not serialize blob
IDs or hydrated raw evidence.

## Visibility and ownership

Every report generated from a public repository has an unguessable public share URL. Anyone who has
that URL can view the report; it is not a private vault. Public reports contain no user identifier.
A signed-in user's history is a private, subject-scoped list of links to reports. Removing a history
item deletes only that ownership link, not the cached public report or another user's link.

## Retention and deletion

The operational policy is 90 days for anonymous/authenticated usage counters, processed webhook
receipts, revoked API keys, and unowned cached public reports. Reports linked to at least one
signed-in history are preserved; after the final link is removed, they become eligible at the next
cleanup if already older than 90 days. Run
`python -m app.maintenance --days 90` to preview exact counts and add `--execute` only in an approved
maintenance window. The command uses one transaction and never removes owned reports.

Users can remove individual history links in the account interface. Supabase account deletion and
full subject-data erasure are operational requests; operators must delete the user's history links
and authenticated usage row, then follow Supabase's account-deletion procedure. Database backups
may retain deleted rows until backup expiry. Platform logs and database backups should be configured
for no more than 30 days where provider controls permit it.

## Analytics boundary

Optional product analytics is disabled unless a server-side provider is configured. Only named
lifecycle events and categorical allowlisted fields may be exported. Authorization headers,
cookies, access tokens, repository identities or evidence, passwords, database URLs, emails, pasted
errors, and request bodies are excluded. A new data recipient requires privacy and security review.

## Product-tool inputs

Pasted error text is processed in memory for the request and is neither persisted nor included in
application logs or responses. Comparison stores no new data. Discovery sends the explicit search
filters to GitHub and returns normalized public metadata; RepoLive does not persist search history.
The proposed local-system protocol prohibits hostnames, usernames, IP addresses, hardware serials,
environment-variable values, file listings, installed-package inventories, and process listings.

API keys are stored only as keyed hashes. Stripe stores payment details; RepoLive stores customer
and subscription identifiers plus status. GitHub user and installation tokens remain in memory and
are not persisted.
