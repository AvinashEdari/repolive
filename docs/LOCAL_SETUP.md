# Local setup

## One-click VS Code startup

Open the repository folder in VS Code, ensure Docker Desktop is running, and press `Ctrl+Shift+B`.
The default **RepoLive: Start everything** task prepares missing dependencies, migrates the local
SQLite database, starts the web app, API, preview router and worker, waits for readiness, and opens
`http://localhost:3000/analyze`. From **Terminal → Run Task**, use **RepoLive: Stop everything** to
stop only the processes started by this task, or **RepoLive: Service status** to inspect them.

The first run can take several minutes while Python/npm dependencies and preview images download.
Local authentication bypass is enabled only for this development task and is forbidden in production.
The task also raises the local-only preview-period allowance while retaining a one-active-preview
concurrency limit; production entitlement limits are unchanged.

Use Node.js 24+, npm 11+, and Python 3.11+. Create `.venv-local`; workstation-specific verification
environments are ignored and must not be committed.

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

Authentication is optional locally. To exercise it, use a real non-production Supabase project and
set `SUPABASE_URL` and `SUPABASE_JWT_AUDIENCE` for the API plus
`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for the browser. Do not use or expose
the service-role key. Without those variables, anonymous analysis and public reports remain usable.
