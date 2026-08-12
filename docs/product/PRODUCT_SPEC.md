# Product specification

RepoLive helps technical and non-technical users understand, evaluate, and set up public
repositories. A public GitHub URL produces an evidence-backed report covering identity, purpose,
languages, dependencies, runtimes, tooling, important files, quality signals, setup guidance,
compatibility conditions, strengths, risks, missing essentials, unknowns, and transparent scores.

Deterministic evidence is authoritative. Repository-provided commands are labeled separately from
RepoLive-derived guidance and are displayed only. Optional explanations are supplemental and the
product remains fully functional while their provider is disabled. Anonymous analysis uses a
configurable allowance and unchanged commit/version reports are reused.

## Product tools

- Error diagnosis accepts at most 20,000 characters, classifies supported error signatures, and
  combines them with an existing report's evidence. It does not execute or persist the supplied
  text, and every response includes confidence, safe checks, and unknowns.
- Comparison accepts two distinct public analysis IDs and compares the cached deterministic
  reports. It does not make new provider requests or claim measured installation difficulty.
- Discovery accepts bounded topic, language, and project-type filters, makes one official GitHub
  search request, and returns at most ten safe normalized links. Its score explains relevance,
  topic, license, activity state, fork state, and a capped star contribution.
- Local system detection remains a protocol design only. The website cannot inspect a visitor's
  machine; a future client would require explicit execution and reviewable consent.

## SaaS foundation

Free and Pro capabilities are described by centralized entitlements. Billing uses Stripe-hosted
pages only. Authenticated users can create revocable API keys for safe versioned report retrieval;
keys never expose raw evidence. Admin summaries are aggregate and require an explicit server-side
subject allowlist. Organizations and GitHub App installations have persistence and authorization
boundaries, but team invitations, shared-history UI, and private-repository analysis remain disabled
until their external launch gates are complete.
