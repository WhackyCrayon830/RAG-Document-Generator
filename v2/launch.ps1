param(
    [switch]$Help,
    [switch]$Interactive,
    [switch]$Config,           # alias for -Interactive
    [switch]$ConfigOnly,
    [switch]$ShowConfig,
    [switch]$SkipModelPull,
    [switch]$NoBrowser,
    [switch]$Test,
    [switch]$NoCelery,
    [switch]$NoRedis,
    [string]$EnvName = ""
)

# ─── Help ────────────────────────────────────────────────────────────────────
if ($Help) {
    Write-Host ""
    Write-Host "+--------------------------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host "|   Offline RAG Document Generator – Launcher Help                        |" -ForegroundColor Cyan
    Write-Host "+--------------------------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "USAGE" -ForegroundColor White
    Write-Host "  .\launch.ps1 [flags]"
    Write-Host ""
    Write-Host "FLAGS" -ForegroundColor White
    Write-Host "  (none)            Launch with default / previously saved configuration"
    Write-Host "  -Interactive      Run the interactive setup wizard before launching"
    Write-Host "  -Config           Alias for -Interactive"
    Write-Host "  -ConfigOnly       Run setup wizard, save config, then exit (no launch)"
    Write-Host "  -ShowConfig       Print active configuration and exit"
    Write-Host "  -SkipModelPull    Skip automatic Ollama model pull/check"
    Write-Host "  -NoBrowser        Do not open the browser after launch"
    Write-Host "  -NoCelery         Do not start the Celery background worker"
    Write-Host "  -NoRedis          Run without Redis (tasks run eagerly, no async progress bar)"
    Write-Host "  -Test             Run the pytest test suite and exit"
    Write-Host "  -EnvName <name>   Override the conda environment name"
    Write-Host "  -Help             Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES" -ForegroundColor White
    Write-Host "  .\launch.ps1                    # Start with defaults"
    Write-Host "  .\launch.ps1 -Interactive       # Configure then start"
    Write-Host "  .\launch.ps1 -NoBrowser         # Start without opening browser"
    Write-Host "  .\launch.ps1 -SkipModelPull     # Start without pulling Ollama models"
    Write-Host "  .\launch.ps1 -NoCelery          # Start without background task worker"
    Write-Host "  .\launch.ps1 -Test              # Run test suite"
    Write-Host "  .\launch.ps1 -ShowConfig        # Print current config"
    Write-Host "  .\launch.ps1 -ConfigOnly        # Save config without launching"
    Write-Host ""
    exit 0
}

# -Config is an alias for -Interactive
if ($Config) { $Interactive = $true }

# ─── Helper: find conda ──────────────────────────────────────────────────────
function Get-CondaCommandQuick {
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

# ─── Test mode ───────────────────────────────────────────────────────────────
if ($Test) {
    Write-Host "Running tests..." -ForegroundColor Cyan
    $conda = Get-CondaCommandQuick
    if (-not $conda) {
        Write-Host "Error: Conda not found." -ForegroundColor Red
        exit 1
    }
    $envName = if ($EnvName) { $EnvName } else { "rag_document_generator" }
    Write-Host "Using conda environment: $envName" -ForegroundColor Yellow
    & $conda run -n $envName pytest tests/ -v --cov=backend --cov-report=html
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "All tests passed! HTML report: htmlcov/index.html" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Tests failed!" -ForegroundColor Red
        exit 1
    }
    exit 0
}

# ─── Streamlit config ────────────────────────────────────────────────────────
$streamlitDir  = Join-Path $env:USERPROFILE ".streamlit"
$streamlitConf = Join-Path $streamlitDir "config.toml"
if (-not (Test-Path $streamlitDir)) {
    New-Item -ItemType Directory -Path $streamlitDir | Out-Null
}
if (-not (Test-Path $streamlitConf)) {
@"
[logger]
level = "error"

[client]
showErrorDetails = false
toolbarMode = "minimal"

[global]
dataFrameSerialization = "arrow"

[browser]
gatherUsageStats = false
serverAddress = "localhost"

[server]
headless = true
runOnSave = false
port = 8501
"@ | Set-Content $streamlitConf
}

# ─── Celery worker ───────────────────────────────────────────────────────────
if (-not $NoCelery -and -not $NoRedis) {
    Write-Host "Starting background task worker..." -ForegroundColor Cyan
    $condaCmd = Get-CondaCommandQuick
    $runEnvName = if ($EnvName) { $EnvName } else { "rag_document_generator" }
    Start-Process -PassThru -WindowStyle Hidden -FilePath "powershell.exe" `
        -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -Command `"cd '$PSScriptRoot'; `$env:PYTHONUNBUFFERED='1'; & '$condaCmd' run -n '$runEnvName' celery -A workers.celery_app worker --loglevel=info --concurrency=4`"" | Out-Null
    Write-Host "  Celery worker started (4 concurrent slots)." -ForegroundColor Green
} elseif ($NoRedis) {
    Write-Host "  NoRedis mode: Celery tasks will run synchronously in the FastAPI process." -ForegroundColor Yellow
}

# ─── Delegate to scripts/launch.ps1 ─────────────────────────────────────────
$launcherPath = Join-Path $PSScriptRoot "scripts\launch.ps1"
& $launcherPath `
    -Interactive:$Interactive `
    -ConfigOnly:$ConfigOnly `
    -ShowConfig:$ShowConfig `
    -SkipModelPull:$SkipModelPull `
    -NoBrowser:$NoBrowser `
    -NoRedis:$NoRedis `
    -EnvName $EnvName
