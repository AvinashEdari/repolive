# Preview execution threat model

Status: design and local proof-of-concept controls. Hostile public production remains prohibited.

## Assets and trust boundaries

Repositories, Git metadata, archives, manifests, dependencies, scripts, artifacts, logs, HTTP
responses and preview visitors are hostile. Control-plane credentials, database access, GitHub
credentials, host files, runtime sockets, cloud metadata, internal networks and other previews are
protected assets. Boundaries exist at browser/API, API/database queue, worker/source provider,
worker/runtime provider, sandbox/network, and preview router/browser.

The API never executes repository material. The worker receives only repository identity, an exact
40-character SHA, an opaque preview ID and non-secret limits. No RepoLive, Supabase, database,
billing or GitHub service secret enters a sandbox.

## Threats and required mitigations

| Threat | Control / disposition |
| --- | --- |
| Malicious Dockerfiles, Compose, binaries and arbitrary commands | Unsupported and rejected; only a trusted static profile is selected. |
| Package lifecycle and supply-chain attacks | Node builds are not in stage 1; future builds require immutable images, controlled registries and egress proxying. |
| Fork bombs, process/file/open-file exhaustion | Non-root sandbox, PID/CPU/memory/file/open-file limits, read-only root and absolute timeout. |
| Memory/disk exhaustion, infinite builds, mining | Memory/CPU/disk quotas, bounded checkout/logs, timeouts, expiration and forced destruction; provider telemetry still required. |
| Network scanning, SSRF, metadata, DNS rebinding, exfiltration and reverse shells | Runtime egress is disabled. Production requires provider/network-layer deny rules for loopback, RFC1918, link-local, metadata, control-plane and cross-preview networks plus DNS/connection limits. Application validation alone is insufficient. |
| Privilege escalation, escape, host socket/files | Drop all capabilities, no-new-privileges, no privileged/host namespaces or mounts, no runtime socket, non-root UID, seccomp/provider policy. Plain Docker remains development-only. |
| Cross-preview access | Per-sandbox network boundary and opaque one-to-one routing; production provider validation remains open. |
| Log/control/ANSI injection and secret leakage | Strip ANSI/control bytes, redact token/cookie/credential patterns, cap lines/bytes and store safe categories only. |
| Stored/reflected XSS and malicious/phishing content | Never embed previews in RepoLive; use a separate registrable domain, no shared cookies, generic unavailable pages, abuse reporting and takedown. |
| Preview-domain cookie/custom-domain attacks | No custom domains; separate registrable domain; never set parent-domain cookies. Local loopback routing is not equivalent. |
| Illegal/harmful content | Authentication, quota, short expiry, audit events, disable switch, reporting/takedown process and provider controls. |
| Abandoned/leaked sandboxes | Leases, heartbeat, expiry, idempotent stop/destroy and exact-label reconciliation. Alerting is required in staging/production. |
| GitHub/registry denial of service | Authentication, per-period/concurrency limits, exact-SHA archive retrieval, timeouts, byte limits and future controlled caches. |

Residual risk includes runtime and kernel vulnerabilities, provider compromise, novel covert
channels, abuse at scale, and content moderation. Controlled staging requires a hardened execution
provider and network-policy verification. Hostile public production additionally requires external
penetration testing, incident drills, capacity/cost controls, legal review and a launch review.
