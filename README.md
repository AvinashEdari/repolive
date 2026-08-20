# RepoLive

RepoLive turns public source repositories into evidence-based reports. Repository analysis never
executes code. A separate, disabled-by-default local preview proof of concept can serve eligible
root-level static HTML and approved locked npm frontend repositories through a dedicated worker and disposable sandbox.

The product shell is available at `/`; the full analysis workspace is available at `/analyze`.
Successful analyses receive durable public IDs and render at `/analysis/{public_id}`.

## Product status

The locally verified MVP analyzes public GitHub repositories without cloning or executing them.
It supports bounded evidence retrieval, multi-ecosystem dependency/runtime parsing, setup and
compatibility guidance, explainable scores, durable reports, quotas, and public share pages.
Supabase authentication, PostgreSQL persistence, and the Vercel/Render staging deployment are
configured and verified. GitHub Actions, structured safe logs, SEO routes, legal drafts, and
operations runbooks are included; professional legal review and distributed abuse controls remain
production-launch requirements.

Stage 7 adds a `/tools` workspace for deterministic pasted-error diagnosis, side-by-side
comparison of cached public analyses, and bounded public-repository discovery through GitHub's
official API. A future local compatibility client is designed but intentionally not implemented.

## Local development

Prerequisites: Node.js 24+, npm 11+, and Python 3.11+.

```powershell
python -m venv .venv-local
.venv-local\Scripts\python -m pip install -e "apps/api[dev]"
cmd /c npm install
```

Apply migrations from `apps/api` with
`..\..\.venv-local\Scripts\python -m alembic -c alembic.ini upgrade head`.
Run the API with `.venv-local\Scripts\python -m uvicorn app.main:app --app-dir apps/api --reload`
and the web app with `cmd /c npm run dev:web`.

## Verification

```powershell
.venv-local\Scripts\python -m pytest apps/api/tests
.venv-local\Scripts\python -m ruff check apps/api
.venv-local\Scripts\python -m mypy apps/api/app
cmd /c npm run check
cmd /c npm run build:web
```

See [PROJECT_STATE.md](docs/milestones/PROJECT_STATE.md) for exact implementation status and limitations.
See [LOCAL_SETUP.md](docs/LOCAL_SETUP.md), [ENVIRONMENT.md](docs/ENVIRONMENT.md), and
[DEPLOYMENT.md](docs/DEPLOYMENT.md) for operational details.

## Local isolated-preview proof of concept

Preview execution is off by default. After reviewing the isolated-preview architecture and threat
model, set `PREVIEW_EXECUTION_ENABLED=true`, `PREVIEW_QUEUE_PROVIDER=database`,
`PREVIEW_RUNTIME_PROVIDER=local_docker`, and
`PREVIEW_ROUTER_BASE_URL=http://preview.localhost:8081`. From `apps/api`, start the router with
`python -m uvicorn app.previews.router:app --host 127.0.0.1 --port 8081` and start the worker
separately with `python -m app.previews.worker`. The API never starts either process. Docker should
be rootless where available. This adapter is not approved for production or hostile multi-tenancy.
# repolive
