# Local setup

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
