
param(
    [switch]$Config,
    [switch]$ConfigOnly,
    [switch]$ShowConfig,
    [switch]$SkipModelPull,
    [switch]$NoBrowser,
    [switch]$Test,
    [switch]$NoCelery,
    [string]$EnvName = ""
)

# Helper function to get conda command
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

if ($Test) {
    Write-Host "Running tests..." -ForegroundColor Cyan
    $Root = Resolve-Path (Join-Path $PSScriptRoot "..")
    $conda = Get-CondaCommandQuick
    if (-not $conda) {
        Write-Host "Error: Conda not found. Please install Miniconda or Anaconda." -ForegroundColor Red
        exit 1
    }
    
    $envName = "rag_document_generator"
    Write-Host "Using conda environment: $envName" -ForegroundColor Yellow
    Write-Host ""
    
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

# Build parameters to pass to scripts/launch.ps1
# Note: We pass parameters directly without array splatting to avoid
# PowerShell interpreting flag names as positional values

# Check if Celery worker should be started in background
$startCelery = -not $NoCelery

# Start Celery worker in background if requested
if ($startCelery) {
    Write-Host "Starting background task worker..." -ForegroundColor Cyan
    $celeryProcess = Start-Process -PassThru -WindowStyle Hidden -FilePath "powershell" `
        -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot' && celery -A workers.celery_app worker --loglevel=warning --concurrency=2`""
}

$streamlitDir = Join-Path $env:USERPROFILE ".streamlit"
$configFile = Join-Path $streamlitDir "config.toml"

if (-not (Test-Path $streamlitDir)) {
    New-Item -ItemType Directory -Path $streamlitDir | Out-Null
}

if (-not (Test-Path $configFile)) {
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
runOnSave = true
port = 8501
"@ | Set-Content $configFile
}

# Execute the actual launcher with direct parameter passing
$launcherPath = Join-Path $PSScriptRoot "scripts\launch.ps1"
& $launcherPath -Config:$Config -ConfigOnly:$ConfigOnly -ShowConfig:$ShowConfig `
                 -SkipModelPull:$SkipModelPull -NoBrowser:$NoBrowser `
                 -EnvName $EnvName
