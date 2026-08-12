# SaaS architecture

Plans resolve through one `Entitlements` boundary; analyzers contain no pricing rules. Only active or
trialing subscription state grants Pro. Stripe uses hosted Checkout and Billing Portal sessions,
five-minute signed webhooks, and durable event IDs for idempotency. Card data never reaches RepoLive.

API keys are shown once, HMAC-hashed with a server pepper, revocable, and quota checked. External
responses contain derived contracts and public metadata, never hydrated evidence content.

Organizations have an owner, owner/admin/member roles, a plan, and explicit shared-analysis links.
The initial API exposes creation only; invitations and shared-history UI stay disabled pending their
authorization workflows.

GitHub App support validates user access to an installation and uses short-lived installation
tokens. PATs are not stored. Analysis persistence has an explicit public/private visibility and
owner boundary, and every unauthenticated/public lookup filters to public records. Private analysis
remains disabled until real credentials, repository selection, owner-scoped ingestion/history, and
cross-user tests are configured. Repository code is never executed in any plan.
