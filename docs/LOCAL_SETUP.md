# Local setup

Use Node.js 24+, npm 11+, and Python 3.11+. The existing `.venv` is stale on this workstation;
create `.venv-local` or use the verified ignored `.venv311` environment.

From the repository root:

```powershell
python -m venv .venv-local
.venv-local\Scripts\python -m pip install -e "apps/api[dev]"
cmd /c npm install
```

Copy `.env.example` to `.env`, then migrate the database:

```powershell
Set-Location apps/api
..\..\.venv-local\Scripts\python -m alembic -c alembic.ini upgrade head
Set-Location ../..
```

Run the API and web application in separate terminals:

```powershell
.venv-local\Scripts\python -m uvicorn app.main:app --app-dir apps/api --reload
cmd /c npm run dev:web
```

Open `http://localhost:3000/analyze`. Docker is not required for local verification.
