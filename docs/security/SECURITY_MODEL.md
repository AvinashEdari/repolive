# Security model

Repository URLs and content are untrusted. Retrieval must enforce allowlisted hosts, safe redirects, byte/file/time limits, escaped output, and token-safe logging. Repository commands never run on the API host. Execution belongs in a separately isolated service after threat modelling.

Allowlisted evidence files are retrieved by Git object ID with strict count and byte limits.
Malformed base64 is rejected and non-UTF-8 evidence is skipped. Raw evidence content is excluded
from API serialization to avoid reflecting repository-controlled text or environment examples.
