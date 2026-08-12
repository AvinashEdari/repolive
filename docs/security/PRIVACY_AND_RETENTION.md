# Privacy and data retention

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

The current MVP retains cached public reports, usage counters, and history links until an operator
deletes them or a future retention job is configured. Users can remove individual history links in
the account interface. Supabase account deletion and full subject-data erasure are operational
requests; operators must delete the user's history links and authenticated usage row, then follow
Supabase's account-deletion procedure. Database backups may retain deleted rows until backup expiry.

Before a public production launch, define and automate concrete report, counter, test-account,
database-backup, and platform-log retention periods. Document the jurisdiction and contact path for
access or deletion requests.

## Analytics boundary

RepoLive currently has no application analytics SDK. If analytics or error monitoring is added, do
not capture authorization headers, cookies, access tokens, repository evidence content, passwords,
database URLs, or complete request bodies. Prefer aggregate operational metrics and short-lived,
pseudonymous identifiers. Update this document before enabling a new data recipient.

## Product-tool inputs

Pasted error text is processed in memory for the request and is neither persisted nor included in
application logs or responses. Comparison stores no new data. Discovery sends the explicit search
filters to GitHub and returns normalized public metadata; RepoLive does not persist search history.
The proposed local-system protocol prohibits hostnames, usernames, IP addresses, hardware serials,
environment-variable values, file listings, installed-package inventories, and process listings.
