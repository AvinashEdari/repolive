# Isolated previews architecture

Status: local proof of concept; disabled by default; not approved for hostile multi-tenant production.

RepoLive now separates the control plane (Next.js, FastAPI, authentication, policy, database and
job records) from an execution plane (a separately started worker and disposable sandbox). API
requests only validate policy and enqueue durable database work. They never clone, build, or run a
repository. `PreviewRuntime` and `PreviewQueue` contracts keep provider operations out of routes.

The first profile is deliberately narrow: a public GitHub repository whose analyzed immutable tree
contains a root `index.html`. The trusted runtime serves that checkout with a RepoLive-controlled
static server. Dockerfiles, package scripts, start commands, submodules, LFS, symlinks, arbitrary
ports, secrets, writable persistent volumes, and server-rendered applications are rejected.

```mermaid
flowchart LR
  B["Authenticated browser"] -->|Bearer token| A["FastAPI control plane"]
  A --> P["Preview policy"]
  A --> D[("Preview records and durable queue")]
  W["Dedicated local worker"] -->|lease and heartbeat| D
  W --> G["GitHub immutable archive"]
  W --> R["PreviewRuntime"]
  R --> S["Disposable static sandbox"]
  X["Isolated preview origin/router"] -->|opaque route only| S
```

The database state machine is `requested -> policy_check -> queued -> cloning -> building ->
starting -> ready -> stopping -> destroyed`, with `rejected`, `failed`, `timed_out`, `expired`, and
`canceled` terminal outcomes. Transitions use conditional updates. Events contain sanitized,
bounded messages. A worker lease enables stale-job recovery; retry count and lifetime are bounded.

Local Docker is a developer adapter, not a production security boundary. A production provider
must supply microVM/gVisor/Kata-equivalent isolation, policy-enforced egress, a durable distributed
queue, registrable-domain isolation, TLS routing, distributed abuse controls, metrics and alerts.
Production configuration rejects `local_docker` and fails closed when required providers or routing
configuration are absent.

The router contract maps a cryptographically random routing key to one healthy sandbox. Untrusted
content must use a registrable domain distinct from RepoLive, without shared cookies or browser
storage. The local adapter may expose a loopback-only development URL and therefore does not prove
domain isolation.
