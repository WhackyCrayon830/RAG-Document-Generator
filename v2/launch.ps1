param(
    [switch]$Config,
    [switch]$ConfigOnly,
    [switch]$ShowConfig,
    [switch]$SkipModelPull,
    [switch]$NoBrowser,
    [switch]$Test
)

if ($Test) {
    Write-Host "Running all tests..." -ForegroundColor Cyan
    pytest tests/ -v --cov=backend --cov-report=html
    if ($LASTEXITCODE -eq 0) {
        Write-Host "All tests passed!" -ForegroundColor Green
    } else {
        Write-Host "Tests failed!" -ForegroundColor Red
        exit 1
    }
    exit 0
}

$normalized = foreach ($arg in $args) {
    switch ($arg) {
        "--config" { "-Config" }
        "--config-only" { "-ConfigOnly" }
        "--show-config" { "-ShowConfig" }
        "--skip-model-pull" { "-SkipModelPull" }
        "--no-browser" { "-NoBrowser" }
        "--test" { "-Test" }
        default { $arg }
    }
}

# Check if Celery worker should be started in background
$startCelery = $true
if ($args -contains "--no-celery" -or $args -contains "-NoCelery") {
    $startCelery = $false
}

# Start Celery worker in background if requested
if ($startCelery) {
    Write-Host "Starting Celery worker in background..." -ForegroundColor Yellow
    $celeryProcess = Start-Process -PassThru -WindowStyle Hidden -FilePath "powershell" `
        -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot' && celery -A workers.celery_app worker --loglevel=info`""
}

& "$PSScriptRoot\scripts\launch.ps1" @normalized
