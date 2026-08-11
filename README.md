# RepoLive

RepoLive turns public source repositories into evidence-based, beginner-friendly technical reports. It validates GitHub URLs, ingests bounded public metadata and allowlisted textual evidence, and deterministically reports languages, dependencies, runtimes, tooling, important files, quality signals, and explainable scores. It does not execute repository code.

The product shell is available at `/`; the full analysis workspace is available at `/analyze`.
Successful analyses receive durable public IDs and render at `/analysis/{public_id}`.

## Product status

The locally verified MVP analyzes public GitHub repositories without cloning or executing them.
It supports bounded evidence retrieval, multi-ecosystem dependency/runtime parsing, setup and
compatibility guidance, explainable scores, durable reports, quotas, and public share pages.
Supabase authentication and cloud deployment are not configured.

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
