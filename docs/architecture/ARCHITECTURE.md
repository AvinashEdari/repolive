# Architecture

The initial modular monolith has a Next.js client and FastAPI API. The API separates routes, provider adapters, typed schemas, ingestion, and composable analyzers. Untrusted repository code is never executed by the API.
