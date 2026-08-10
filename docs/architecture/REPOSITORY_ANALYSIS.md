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

## Next pipeline milestone

Ingest a strictly allowlisted, size-bounded set of textual manifests. Dependency, framework,
documentation, test, CI, and runtime analyzers can then parse file contents without cloning or
executing the repository.

Pipeline: validation, provider retrieval, bounded ingestion, deterministic analyzers, explainable scoring, persistence, and presentation. Facts retain evidence and confidence.
