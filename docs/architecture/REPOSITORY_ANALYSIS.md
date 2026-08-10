# Repository analysis

## Implemented ingestion boundary

The API validates an HTTPS `github.com/{owner}/{repository}` URL, then asks the provider for a
bounded snapshot. The GitHub provider retrieves repository metadata and the recursive Git tree
through the official REST API. It returns provider-neutral typed models and never clones or
executes repository code.

Ingestion rejects truncated GitHub tree responses and snapshots exceeding configured file-count
or known-byte limits. Provider failures are explicit; the API does not turn partial data into a
successful analysis.

## Next pipeline milestone

Composable deterministic analyzers will consume the snapshot to classify languages, important
files, frameworks, dependency manifests, documentation, tests, CI, and runtime evidence.

Pipeline: validation, provider retrieval, bounded ingestion, deterministic analyzers, explainable scoring, persistence, and presentation. Facts retain evidence and confidence.
