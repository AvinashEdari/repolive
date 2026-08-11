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

Direct dependency parsing also supports Cargo, Go modules, Maven, Gradle, Ruby Gemfiles,
Composer, and .NET project files. Setup commands are generated only from recognized manifests
or displayed verbatim from declared package scripts; their origin and source path remain attached.
Compatibility conclusions are conditional or unknown unless repository evidence proves them.

## Implemented persistence and sharing

Successful reports are stored through a SQLAlchemy-backed repository with random public IDs.
SQLite is the verified local database. Anonymous usage is counted transactionally against an
HTTP-only browser identifier and the configurable free-analysis allowance. Stored reports are
available from the API and the server-rendered `/analysis/{public_id}` web route.

Repository metadata includes the default-branch commit SHA. The store normalizes provider,
owner, and repository identity and reuses a report only when both commit SHA and
`ANALYSIS_VERSION` match. Alembic owns the production schema; automatic table creation is
disabled in production.

## Next pipeline milestone

Connect and verify a user-authorized Supabase project, then add authenticated history and private
repository authorization. Expand lockfile conflict analysis and README setup-section extraction
without treating prose as an executable instruction source.

Pipeline: validation, provider retrieval, bounded ingestion, deterministic analyzers, explainable scoring, persistence, and presentation. Facts retain evidence and confidence.
