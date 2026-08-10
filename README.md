# RepoLive

RepoLive turns public source repositories into evidence-based, beginner-friendly technical reports. This clean rebuild currently contains the first verified product foundation; it does not execute repository code.

## Local development

Prerequisites: Node.js 24+, npm 11+, and Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "apps/api[dev]"
cmd /c npm install
```

Run the API with `.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --reload` and the web app with `cmd /c npm run dev:web`.

## Verification

```powershell
.venv\Scripts\python -m pytest apps/api/tests
.venv\Scripts\python -m ruff check apps/api
.venv\Scripts\python -m mypy apps/api/app
cmd /c npm run check
cmd /c npm run build:web
```

See [PROJECT_STATE.md](docs/milestones/PROJECT_STATE.md) for exact implementation status and limitations.

