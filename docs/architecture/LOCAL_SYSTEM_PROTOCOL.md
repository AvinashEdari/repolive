# Future local-system detection protocol

Status: architecture only. RepoLive's website does not inspect the user's machine.

## Consent model

A future open-source CLI or local agent must be downloaded and run deliberately by the user. Before
collecting anything, it must display the exact fields, explain why each is needed, show the target
RepoLive origin, and require an affirmative one-time confirmation. It must support `--dry-run` to
print the payload without sending it and default to no persistence. The website must never trigger
collection, scan files, enumerate installed applications, or infer machine details through browser
fingerprinting.

## Minimum schema

```json
{
  "schema_version": "1",
  "consent": true,
  "operating_system": "Windows | Linux | macOS",
  "cpu_architecture": "x86_64 | arm64 | x86",
  "runtimes": {
    "python": "3.12.2",
    "node": "24.1.0",
    "java": "21"
  },
  "docker_available": true
}
```

Only runtime keys relevant to the selected analysis should be requested. RAM, storage, GPU model,
and GPU memory are optional and should be omitted unless the repository contains explicit matching
requirements and the user opts in. Hostname, username, IP address, device identifiers, environment
variables, file paths, process lists, network interfaces, installed-package inventories, shell
history, and repository contents are prohibited.

## Protocol

1. The user copies a public analysis ID into the local CLI.
2. The CLI fetches the public report and derives the minimum relevant fields locally.
3. The CLI displays a consent preview and optionally emits JSON with `--dry-run`.
4. With consent, it sends one HTTPS `POST` to
   `/api/v1/analyses/{public_id}/compatibility` using the existing bounded compatibility schema.
5. The API validates the payload, computes a deterministic response, and does not store the machine
   profile. Logs contain the public analysis ID, outcome category, request ID, and duration only.

No access token is required for public compatibility. A future authenticated convenience flow must
not bind machine data to account history unless a separate explicit opt-in and deletion control are
designed.

## Security and privacy requirements

- Publish source and reproducible release checksums for the CLI.
- Pin the official API origin and require normal TLS validation.
- Never request administrator/root privileges for detection.
- Never execute repository commands or load repository code.
- Bound payload size and runtime version strings; reject unknown fields.
- Provide local deletion instructions and avoid telemetry by default.
- Threat-model update, replay, proxy, and malicious-report attacks before implementation.
