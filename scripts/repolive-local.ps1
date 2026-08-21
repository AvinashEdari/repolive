param(
    [ValidateSet("Start", "Stop", "Status")]
    [string]$Action = "Start"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDirectory = Join-Path $RepoRoot ".local-run"
$StateFile = Join-Path $RunDirectory "vscode-services.json"

function Stop-TrackedServices {
    if (-not (Test-Path -LiteralPath $StateFile)) { return }
    $entries = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json
    foreach ($entry in $entries) {
        $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if ($null -eq $process) { continue }
        if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$entry.start_time_ticks) {
            Write-Warning "Skipped reused process ID $($entry.pid)."
            continue
        }
        & taskkill.exe /PID $entry.pid /T /F *> $null
    }
    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
}

function Get-ServiceStatus {
    if (-not (Test-Path -LiteralPath $StateFile)) {
        return @()
    }
    $entries = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json
    return @($entries | ForEach-Object {
        $process = Get-Process -Id $_.pid -ErrorAction SilentlyContinue
        [pscustomobject]@{
            Service = $_.name
            PID = $_.pid
            Running = $null -ne $process -and
                $process.StartTime.ToUniversalTime().Ticks -eq [long]$_.start_time_ticks
        }
    })
}

if ($Action -eq "Stop") {
    Stop-TrackedServices
    Write-Host "RepoLive local services stopped."
    exit 0
}

if ($Action -eq "Status") {
    $status = Get-ServiceStatus
    if ($status.Count -eq 0) { Write-Host "RepoLive is not running from the VS Code task." }
    else { $status | Format-Table -AutoSize }
    exit 0
}

New-Item -ItemType Directory -Path $RunDirectory -Force | Out-Null
Stop-TrackedServices

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 24 or newer is required."
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm is required."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required for repository previews."
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Start Docker Desktop, then run this task again." }

$Python = Join-Path $RepoRoot ".venv-vscode\Scripts\python.exe"
$PythonIsValid = $false
if (Test-Path -LiteralPath $Python) {
    $VenvConfig = Join-Path $RepoRoot ".venv-vscode\pyvenv.cfg"
    $BaseExecutable = if (Test-Path -LiteralPath $VenvConfig) {
        $line = Get-Content -LiteralPath $VenvConfig | Where-Object { $_ -like "executable = *" } |
            Select-Object -First 1
        if ($line) { $line.Substring("executable = ".Length).Trim() } else { $null }
    } else { $null }
    $PythonIsValid = $null -ne $BaseExecutable -and (Test-Path -LiteralPath $BaseExecutable)
    if ($PythonIsValid) {
        $PreviousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $BaseExecutable --version *> $null
        $PythonIsValid = $? -and $LASTEXITCODE -eq 0
        $ErrorActionPreference = $PreviousErrorPreference
    }
}
if (-not $PythonIsValid) {
    Remove-Item -LiteralPath (Join-Path $RepoRoot ".venv-vscode") -Recurse -Force `
        -ErrorAction SilentlyContinue
    $SystemPython = $null
    foreach ($Candidate in @(where.exe python 2>$null)) {
        if (-not (Test-Path -LiteralPath $Candidate)) { continue }
        $PreviousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" `
            *> $null
        $CandidateWorks = $? -and $LASTEXITCODE -eq 0
        $ErrorActionPreference = $PreviousErrorPreference
        if ($CandidateWorks) { $SystemPython = $Candidate; break }
    }
    if (-not $SystemPython) { throw "Python 3.11 or newer is required." }
    & $SystemPython -m venv (Join-Path $RepoRoot ".venv-vscode")
}

$PreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "import fastapi, alembic, sqlalchemy" 2>$null
$DependencyProbeExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorPreference
if ($DependencyProbeExitCode -ne 0) {
    & $Python -m pip install -e "$RepoRoot\apps\api[dev]"
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "node_modules"))) {
    & npm.cmd install --prefix $RepoRoot
}

$DatabasePath = (Join-Path $RepoRoot "repolive-local-run.db").Replace("\", "/")
$env:APP_ENV = "development"
$env:PYTHONPATH = Join-Path $RepoRoot "apps\api"
$env:DATABASE_URL = "sqlite:///$DatabasePath"
$env:WEB_ORIGIN = "http://localhost:3000"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
$env:PREVIEW_EXECUTION_ENABLED = "true"
$env:PREVIEW_QUEUE_PROVIDER = "database"
$env:PREVIEW_RUNTIME_PROVIDER = "local_docker"
$env:PREVIEW_ROUTER_BASE_URL = "http://preview.localhost:8081"
$env:PREVIEW_LOCAL_AUTH_BYPASS = "true"
$env:PREVIEW_PERIOD_LIMIT = "1000"
$env:PREVIEW_MAX_CONCURRENT_PER_USER = "1"
$env:PREVIEW_BUILD_TIMEOUT_SECONDS = "600"
$env:PREVIEW_RUNTIME_SECONDS = "600"
$env:PREVIEW_MEMORY_MB = "1024"
$env:PREVIEW_PIDS_LIMIT = "128"

Push-Location (Join-Path $RepoRoot "apps\api")
try {
    & $Python -m alembic -c alembic.ini upgrade head
} finally {
    Pop-Location
}

$services = @(
    @{ Name = "api"; File = $Python; Args = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"); Work = (Join-Path $RepoRoot "apps\api") },
    @{ Name = "router"; File = $Python; Args = @("-m", "uvicorn", "app.previews.router:app", "--host", "127.0.0.1", "--port", "8081"); Work = (Join-Path $RepoRoot "apps\api") },
    @{ Name = "worker"; File = $Python; Args = @("-m", "app.previews.worker"); Work = (Join-Path $RepoRoot "apps\api") },
    @{ Name = "web"; File = "npm.cmd"; Args = @("run", "dev:web"); Work = $RepoRoot }
)

$state = @()
foreach ($service in $services) {
    $process = Start-Process -FilePath $service.File -ArgumentList $service.Args `
        -WorkingDirectory $service.Work -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $RunDirectory "$($service.Name).out.log") `
        -RedirectStandardError (Join-Path $RunDirectory "$($service.Name).err.log")
    $state += [pscustomobject]@{
        name = $service.Name
        pid = $process.Id
        start_time_ticks = $process.StartTime.ToUniversalTime().Ticks
    }
}
$state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8

$deadline = (Get-Date).AddSeconds(45)
do {
    try {
        $apiReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/v1/preview-capabilities" -TimeoutSec 2).StatusCode -eq 200
        $webReady = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3000/analyze" -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $apiReady = $false
        $webReady = $false
    }
    if (-not ($apiReady -and $webReady)) { Start-Sleep -Milliseconds 750 }
} until (($apiReady -and $webReady) -or (Get-Date) -ge $deadline)

if (-not ($apiReady -and $webReady)) {
    Write-Host "Startup failed. Check .local-run/*.err.log." -ForegroundColor Red
    Get-ServiceStatus | Format-Table -AutoSize
    exit 1
}

Write-Host "RepoLive is ready: http://localhost:3000/analyze" -ForegroundColor Green
Start-Process "http://localhost:3000/analyze"
