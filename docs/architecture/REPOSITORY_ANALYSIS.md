# Repository analysis

## Implemented ingestion boundary

The API validates an HTTPS `github.com/{owner}/{repository}` URL, then asks the provider for a
bounded snapshot. The GitHub provider retrieves repository metadata and the recursive Git tree
through the official REST API. It returns provider-neutral typed models and never clones or
executes repository code.

Ingestion rejects truncated GitHub tree responses and snapshots exceeding configured file-count
or known-byte limits. Provider failures are explicit; the API does not turn partial data into a
successful analysis.

## Implemented deterministic pipeline

Composable analyzers now classify supported languages by extension and known bytes, excluding
common generated/vendor directories. Separate analyzers identify important files and high-
confidence technology markers such as framework configuration, package-manager locks, build
tools, containers, and CI workflows. Every finding retains concrete file-path evidence.

The API returns the original immutable snapshot beside the deterministic findings. Unknown
repositories receive an honest generic project type rather than a guessed application category.

## Implemented bounded evidence analysis

The provider fetches recognized manifests, README files, environment templates, and CI workflows
by immutable Git blob ID. File count, per-file bytes, aggregate evidence bytes, base64, and UTF-8
are bounded or validated. Evidence contents are analyzer-internal and excluded from API output.

Parsers currently support npm `package.json`, Python `requirements.txt`, PEP 621
`pyproject.toml`, Node/Python/Go/Rust runtime signals, dependency-backed framework detection,
documentation/testing/CI/container signals, and two explainable score categories.

## Implemented persistence and sharing

Successful reports are stored through a SQLAlchemy-backed repository with random public IDs.
SQLite is the verified local database. Anonymous usage is counted transactionally against an
HTTP-only browser identifier and the configurable free-analysis allowance. Stored reports are
available from the API and the server-rendered `/analysis/{public_id}` web route.

## Next pipeline milestone

Add Alembic migrations and the PostgreSQL driver before connecting a Supabase project. Then
expand Cargo, Go, Maven, and Gradle dependency parsing and produce evidence-based OS-specific
setup steps.

Pipeline: validation, provider retrieval, bounded ingestion, deterministic analyzers, explainable scoring, persistence, and presentation. Facts retain evidence and confidence.
