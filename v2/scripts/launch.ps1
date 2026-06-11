param(
    [Alias("config")]
    [switch]$Config,
    [switch]$ConfigOnly,
    [switch]$ShowConfig,
    [string]$EnvName,
    [int]$BackendPort,
    [int]$FrontendPort,
    [switch]$SkipModelPull,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ConfigPath = Join-Path $Root "storage\cache\launcher-config.json"
$EnvFile = Join-Path $Root "environment.yml"
$DotEnvPath = Join-Path $Root ".env"

if ($PSStyle) {
    $PSStyle.OutputRendering = "Ansi"
}

$C = @{
    Reset = "`e[0m"
    Dim = "`e[2m"
    Bold = "`e[1m"
    Red = "`e[31m"
    Green = "`e[32m"
    Yellow = "`e[33m"
    Blue = "`e[34m"
    Cyan = "`e[36m"
    White = "`e[37m"
    Gray = "`e[90m"
}

function Write-Rule {
    param([string]$Text = "")
    $line = "-" * 76
    Write-Host "$($C.Gray)$line$($C.Reset)"
    if ($Text) {
        Write-Host "$($C.Bold)$($C.Cyan)$Text$($C.Reset)"
    }
}

function Write-Logo {
    Clear-Host
    Write-Host ""
    Write-Host "$($C.Bold)$($C.Cyan)+--------------------------------------------------------------------------+$($C.Reset)"
    Write-Host "$($C.Bold)$($C.Cyan)|$($C.Reset) $($C.Bold)$($C.White)Offline RAG Document Generator$($C.Reset) $($C.Dim)$($C.White)- setup, config, launch$($C.Reset)              $($C.Bold)$($C.Cyan)|$($C.Reset)"
    Write-Host "$($C.Bold)$($C.Cyan)+--------------------------------------------------------------------------+$($C.Reset)"
    Write-Host ""
}

function Step { param([string]$Text) Write-Host "$($C.Blue)>$($C.Reset) $($C.Bold)$Text$($C.Reset)" }
function Ok { param([string]$Text) Write-Host "  $($C.Green)OK$($C.Reset)  $Text" }
function Warn { param([string]$Text) Write-Host "  $($C.Yellow)!!$($C.Reset)  $Text" }
function Fail { param([string]$Text) Write-Host "  $($C.Red)XX$($C.Reset)  $Text" }

function Default-Config {
    return [ordered]@{
        user_name = $env:USERNAME
        workspace_name = "RAG Document Generator"
        conda_env_name = "rag_document_generator"
        backend_port = 8000
        frontend_port = 8501
        open_browser = $true
        skip_model_pull = $false
        app_storage_dir = "storage"
        ollama_base_url = "http://localhost:11434"
        postgres_host = "localhost"
        postgres_port = 5432
        postgres_db = "rag_platform"
        postgres_user = "rag"
        postgres_password = "rag_password"
        qdrant_url = "http://localhost:6333"
        redis_url = "redis://localhost:6379/0"
        max_upload_mb = 200
        generation_timeout_seconds = 1800
        worker_concurrency = 2
        models = [ordered]@{
            embedding = "nomic-embed-text"
            planning = "qwen3:14b"
            writing = "qwen3:14b"
            validation = "gemma3:12b"
            editing = "mistral-small"
        }
        env = [ordered]@{
            USE_OLLAMA = "true"
            BACKEND_URL = "http://localhost:8000"
        }
    }
}

function ConvertTo-Hashtable {
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) {
        $hash = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $hash[$key] = ConvertTo-Hashtable $Value[$key]
        }
        return $hash
    }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [string]) {
        return @($Value | ForEach-Object { ConvertTo-Hashtable $_ })
    }
    if ($Value.PSObject.Properties.Count -gt 0 -and $Value -isnot [string]) {
        $hash = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $hash[$property.Name] = ConvertTo-Hashtable $property.Value
        }
        return $hash
    }
    return $Value
}

function Load-Config {
    $defaults = Default-Config
    if (-not (Test-Path $ConfigPath)) {
        return $defaults
    }
    $loaded = ConvertTo-Hashtable ((Get-Content -Raw -LiteralPath $ConfigPath) | ConvertFrom-Json)
    foreach ($key in $defaults.Keys) {
        if (-not $loaded.Contains($key)) {
            $loaded[$key] = $defaults[$key]
        }
    }
    foreach ($key in $defaults.models.Keys) {
        if (-not $loaded.models.Contains($key)) {
            $loaded.models[$key] = $defaults.models[$key]
        }
    }
    foreach ($key in $defaults.env.Keys) {
        if (-not $loaded.env.Contains($key)) {
            $loaded.env[$key] = $defaults.env[$key]
        }
    }
    return $loaded
}

function Save-Config {
    param($ConfigData)
    New-Item -ItemType Directory -Force -Path (Split-Path $ConfigPath) | Out-Null
    $ConfigData | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
}

function Read-ConfigValue {
    param(
        [string]$Label,
        [object]$Default,
        [ValidateSet("string", "int", "bool")]
        [string]$Type = "string"
    )
    $suffix = if ($null -ne $Default -and "$Default" -ne "") { " [$Default]" } else { "" }
    Write-Host -NoNewline "$($C.Cyan)?$($C.Reset) $Label${suffix}: "
    $raw = Read-Host
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $Default
    }
    switch ($Type) {
        "int" { return [int]$raw }
        "bool" { return ($raw -match "^(y|yes|true|1)$") }
        default { return $raw.Trim() }
    }
}

function Read-EnvVars {
    param($Existing)
    $envVars = [ordered]@{}
    foreach ($key in $Existing.Keys) {
        $envVars[$key] = $Existing[$key]
    }

    Write-Host ""
    Write-Host "$($C.Dim)Add extra environment variables as KEY=value. Press Enter on an empty line when done.$($C.Reset)"
    Write-Host "$($C.Dim)Examples: HTTP_PROXY=http://127.0.0.1:7890, NO_PROXY=localhost,127.0.0.1$($C.Reset)"
    while ($true) {
        Write-Host -NoNewline "$($C.Cyan)?$($C.Reset) env var: "
        $line = Read-Host
        if ([string]::IsNullOrWhiteSpace($line)) {
            break
        }
        if ($line -notmatch "^[A-Za-z_][A-Za-z0-9_]*=") {
            Warn "Use KEY=value format"
            continue
        }
        $parts = $line.Split("=", 2)
        $envVars[$parts[0]] = $parts[1]
    }
    return $envVars
}

function Run-ConfigWizard {
    param($Current)
    Write-Rule "Configuration wizard"
    Write-Host "$($C.Dim)Press Enter to keep the value shown in brackets.$($C.Reset)"
    Write-Host ""

    $Current.user_name = Read-ConfigValue "Your name" $Current.user_name
    $Current.workspace_name = Read-ConfigValue "Workspace name" $Current.workspace_name
    $Current.conda_env_name = Read-ConfigValue "Conda environment name" $Current.conda_env_name
    $Current.backend_port = Read-ConfigValue "Backend port" $Current.backend_port "int"
    $Current.frontend_port = Read-ConfigValue "Streamlit port" $Current.frontend_port "int"
    $Current.open_browser = Read-ConfigValue "Open browser after launch? yes/no" $Current.open_browser "bool"
    $Current.skip_model_pull = Read-ConfigValue "Skip automatic Ollama model pulls? yes/no" $Current.skip_model_pull "bool"
    $Current.app_storage_dir = Read-ConfigValue "App storage directory" $Current.app_storage_dir
    $Current.ollama_base_url = Read-ConfigValue "Ollama base URL" $Current.ollama_base_url

    Write-Rule "Service configuration"
    $Current.postgres_host = Read-ConfigValue "PostgreSQL host" $Current.postgres_host
    $Current.postgres_port = Read-ConfigValue "PostgreSQL port" $Current.postgres_port "int"
    $Current.postgres_db = Read-ConfigValue "PostgreSQL database" $Current.postgres_db
    $Current.postgres_user = Read-ConfigValue "PostgreSQL user" $Current.postgres_user
    $Current.postgres_password = Read-ConfigValue "PostgreSQL password" $Current.postgres_password
    $Current.qdrant_url = Read-ConfigValue "Qdrant URL" $Current.qdrant_url
    $Current.redis_url = Read-ConfigValue "Redis URL" $Current.redis_url
    $Current.max_upload_mb = Read-ConfigValue "Max upload MB" $Current.max_upload_mb "int"
    $Current.generation_timeout_seconds = Read-ConfigValue "Generation timeout seconds" $Current.generation_timeout_seconds "int"
    $Current.worker_concurrency = Read-ConfigValue "Worker concurrency" $Current.worker_concurrency "int"

    Write-Rule "Ollama model roles"
    $Current.models.embedding = Read-ConfigValue "Embedding model" $Current.models.embedding
    $Current.models.planning = Read-ConfigValue "Planning model" $Current.models.planning
    $Current.models.writing = Read-ConfigValue "Writing model" $Current.models.writing
    $Current.models.validation = Read-ConfigValue "Validation model" $Current.models.validation
    $Current.models.editing = Read-ConfigValue "Editing model" $Current.models.editing

    Write-Rule "Environment variables"
    $Current.env.USE_OLLAMA = Read-ConfigValue "USE_OLLAMA" $Current.env.USE_OLLAMA
    $Current.env.BACKEND_URL = "http://localhost:$($Current.backend_port)"
    $Current.env.APP_STORAGE_DIR = $Current.app_storage_dir
    $Current.env.OLLAMA_BASE_URL = $Current.ollama_base_url
    $Current.env.POSTGRES_HOST = $Current.postgres_host
    $Current.env.POSTGRES_PORT = "$($Current.postgres_port)"
    $Current.env.POSTGRES_DB = $Current.postgres_db
    $Current.env.POSTGRES_USER = $Current.postgres_user
    $Current.env.POSTGRES_PASSWORD = $Current.postgres_password
    $Current.env.QDRANT_URL = $Current.qdrant_url
    $Current.env.REDIS_URL = $Current.redis_url
    $Current.env.MAX_UPLOAD_MB = "$($Current.max_upload_mb)"
    $Current.env.GENERATION_TIMEOUT_SECONDS = "$($Current.generation_timeout_seconds)"
    $Current.env.WORKER_CONCURRENCY = "$($Current.worker_concurrency)"
    $Current.env.OLLAMA_EMBEDDING_MODEL = $Current.models.embedding
    $Current.env.OLLAMA_PLANNING_MODEL = $Current.models.planning
    $Current.env.OLLAMA_WRITING_MODEL = $Current.models.writing
    $Current.env.OLLAMA_VALIDATION_MODEL = $Current.models.validation
    $Current.env.OLLAMA_EDITING_MODEL = $Current.models.editing
    $Current.env = Read-EnvVars $Current.env

    Save-Config $Current
    Write-DotEnv $Current
    Ok "Saved launcher config to $ConfigPath"
    Ok "Wrote backend environment file to $DotEnvPath"
    return $Current
}

function Write-DotEnv {
    param($ConfigData)
    $lines = @(
        "# Generated by scripts/launch.ps1",
        "APP_STORAGE_DIR=$($ConfigData.app_storage_dir)",
        "OLLAMA_BASE_URL=$($ConfigData.ollama_base_url)",
        "OLLAMA_PLANNING_MODEL=$($ConfigData.models.planning)",
        "OLLAMA_WRITING_MODEL=$($ConfigData.models.writing)",
        "OLLAMA_VALIDATION_MODEL=$($ConfigData.models.validation)",
        "OLLAMA_EDITING_MODEL=$($ConfigData.models.editing)",
        "OLLAMA_EMBEDDING_MODEL=$($ConfigData.models.embedding)",
        "USE_OLLAMA=$($ConfigData.env.USE_OLLAMA)",
        "POSTGRES_HOST=$($ConfigData.postgres_host)",
        "POSTGRES_PORT=$($ConfigData.postgres_port)",
        "POSTGRES_DB=$($ConfigData.postgres_db)",
        "POSTGRES_USER=$($ConfigData.postgres_user)",
        "POSTGRES_PASSWORD=$($ConfigData.postgres_password)",
        "QDRANT_URL=$($ConfigData.qdrant_url)",
        "REDIS_URL=$($ConfigData.redis_url)",
        "MAX_UPLOAD_MB=$($ConfigData.max_upload_mb)",
        "GENERATION_TIMEOUT_SECONDS=$($ConfigData.generation_timeout_seconds)",
        "WORKER_CONCURRENCY=$($ConfigData.worker_concurrency)"
    )
    Set-Content -LiteralPath $DotEnvPath -Value $lines -Encoding UTF8
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s'`"]") {
        return "'" + ($Text -replace "'", "''") + "'"
    }
    return $Text
}

function Export-EnvCommand {
    param($EnvVars)
    $parts = @()
    foreach ($key in $EnvVars.Keys) {
        $value = "$($EnvVars[$key])" -replace "'", "''"
        $parts += "`$env:$key='$value'"
    }
    return ($parts -join "; ")
}

function Test-Port {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return ($task.Wait(650) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port {
    param([int]$Port, [string]$Name, [int]$TimeoutSeconds = 45)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) {
            Ok "$Name is listening on port $Port"
            return $true
        }
        Start-Sleep -Milliseconds 700
    }
    Fail "$Name did not become ready on port $Port"
    return $false
}

function Get-CondaCommand {
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

function Test-CondaEnv {
    param([string]$Conda, [string]$Name)
    $envs = & $Conda env list 2>$null
    return ($envs -match "^\s*$([regex]::Escape($Name))\s+")
}

function Ensure-CondaEnv {
    param([string]$Conda, [string]$Name)
    Step "Checking conda environment"
    if (Test-CondaEnv $Conda $Name) {
        Ok "Environment '$Name' already exists"
        return
    }
    Warn "Environment '$Name' not found"
    if (-not (Test-Path $EnvFile)) {
        throw "Missing environment file: $EnvFile"
    }
    Step "Creating conda environment from environment.yml"
    & $Conda env create -n $Name -f $EnvFile
    if ($LASTEXITCODE -ne 0) {
        Fail "Conda environment creation failed"
        throw "Conda environment creation failed"
    }
    Ok "Environment '$Name' created"
}

function Get-OllamaModels {
    try {
        $rows = & ollama list 2>$null
        if ($LASTEXITCODE -ne 0) { return @() }
        return $rows | Select-Object -Skip 1 | ForEach-Object { ($_ -split "\s+")[0] } | Where-Object { $_ }
    } catch {
        return @()
    }
}

function Ensure-Ollama {
    param($ConfigData)
    Step "Checking Ollama"
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Warn "Ollama CLI was not found. Install Ollama, then rerun this launcher."
        return $false
    }
    Ok "Ollama CLI found"

    $tagsUrl = "$($ConfigData.ollama_base_url.TrimEnd('/'))/api/tags"
    try {
        $null = Invoke-RestMethod -Uri $tagsUrl -TimeoutSec 3
        Ok "Ollama server is running"
    } catch {
        Warn "Ollama server is not responding. Trying to start it in the background."
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 3
        try {
            $null = Invoke-RestMethod -Uri $tagsUrl -TimeoutSec 8
            Ok "Ollama server started"
        } catch {
            Fail "Ollama server did not start. Open Ollama manually and rerun."
            return $false
        }
    }

    if ($ConfigData.skip_model_pull -or $SkipModelPull) {
        Warn "Skipping model pull check"
        return $true
    }

    Step "Checking local Ollama models"
    $required = @(
        $ConfigData.models.embedding,
        $ConfigData.models.planning,
        $ConfigData.models.writing,
        $ConfigData.models.validation,
        $ConfigData.models.editing
    ) | Select-Object -Unique
    $installed = Get-OllamaModels
    foreach ($model in $required) {
        if ($installed -contains $model) {
            Ok "$model is installed"
        } else {
            Warn "$model is missing. Pulling now; this needs internet during setup."
            & ollama pull $model
            if ($LASTEXITCODE -ne 0) {
                Fail "Could not pull $model"
                throw "Ollama model pull failed: $model"
            }
            Ok "$model installed"
        }
    }
    return $true
}

function Start-ServiceIfNeeded {
    param(
        [string]$Name,
        [int]$Port,
        [string[]]$Command,
        [string]$LogPath,
        $EnvVars
    )
    Step "Checking $Name"
    if (Test-Port $Port) {
        Ok "$Name already running on port $Port"
        return
    }
    if (Test-Path $LogPath) {
        Clear-Content -LiteralPath $LogPath
    }
    $envCommand = Export-EnvCommand $EnvVars
    $commandText = ($Command | ForEach-Object { Quote-Arg "$_" }) -join " "
    $script = "Set-Location '$Root'; $envCommand; $commandText *>&1 | Tee-Object -FilePath '$LogPath'"
    $args = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $script)
    Start-Process -FilePath "powershell.exe" -ArgumentList $args -WorkingDirectory $Root | Out-Null
    Ok "$Name launch command sent"
    if (-not (Wait-Port -Port $Port -Name $Name)) {
        Warn "Recent $Name log:"
        if (Test-Path $LogPath) {
            Get-Content -LiteralPath $LogPath -Tail 24 | ForEach-Object { Write-Host "    $_" }
        }
        throw "$Name failed to start"
    }
}

function Write-ConfigSummary {
    param($ConfigData)
    Write-Rule "Active configuration"
    Write-Host "$($C.Green)User       $($C.Reset) $($ConfigData.user_name)"
    Write-Host "$($C.Green)Workspace  $($C.Reset) $($ConfigData.workspace_name)"
    Write-Host "$($C.Green)Conda env  $($C.Reset) $($ConfigData.conda_env_name)"
    Write-Host "$($C.Green)Backend    $($C.Reset) http://localhost:$($ConfigData.backend_port)"
    Write-Host "$($C.Green)Frontend   $($C.Reset) http://localhost:$($ConfigData.frontend_port)"
    Write-Host "$($C.Green)Ollama     $($C.Reset) $($ConfigData.ollama_base_url)"
    Write-Host "$($C.Green)Postgres   $($C.Reset) $($ConfigData.postgres_host):$($ConfigData.postgres_port)/$($ConfigData.postgres_db)"
    Write-Host "$($C.Green)Qdrant     $($C.Reset) $($ConfigData.qdrant_url)"
    Write-Host "$($C.Green)Redis      $($C.Reset) $($ConfigData.redis_url)"
    Write-Host "$($C.Green)Storage    $($C.Reset) $($ConfigData.app_storage_dir)"
    Write-Host "$($C.Green)Models     $($C.Reset) embed=$($ConfigData.models.embedding), write=$($ConfigData.models.writing)"
    Write-Host "$($C.Gray)Config file $($C.Reset) $ConfigPath"
    Write-Host ""
}

try {
    Write-Logo

    $configData = Load-Config
    if ($EnvName) { $configData.conda_env_name = $EnvName }
    if ($PSBoundParameters.ContainsKey("BackendPort")) { $configData.backend_port = $BackendPort }
    if ($PSBoundParameters.ContainsKey("FrontendPort")) { $configData.frontend_port = $FrontendPort }
    if ($NoBrowser) { $configData.open_browser = $false }
    if ($SkipModelPull) { $configData.skip_model_pull = $true }

    $firstRun = -not (Test-Path $ConfigPath)
    if ($Config -or $firstRun) {
        if ($firstRun) {
            Warn "First run detected. Let's configure the launcher."
        }
        $configData = Run-ConfigWizard $configData
    } else {
        Write-DotEnv $configData
    }

    Write-ConfigSummary $configData
    if ($ShowConfig) {
        $configData | ConvertTo-Json -Depth 8
    }
    if ($ConfigOnly) {
        Ok "Configuration saved. Launch skipped because -ConfigOnly was used."
        exit 0
    }

    $logDir = Join-Path $Root "$($configData.app_storage_dir)\cache\logs"
    $backendLog = Join-Path $logDir "backend.log"
    $frontendLog = Join-Path $logDir "frontend.log"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    Write-Rule "Preflight"
    $conda = Get-CondaCommand
    if (-not $conda) {
        Fail "Conda was not found"
        throw "Install Miniconda or Anaconda, then rerun scripts\launch.ps1"
    }
    Ok "Conda found: $conda"

    Ensure-CondaEnv -Conda $conda -Name $configData.conda_env_name
    Ensure-Ollama $configData | Out-Null

    Write-Rule "Services"
    $backendEnv = ConvertTo-Hashtable $configData.env
    $backendEnv.BACKEND_URL = "http://localhost:$($configData.backend_port)"
    $backendEnv.APP_STORAGE_DIR = $configData.app_storage_dir
    $backendEnv.OLLAMA_BASE_URL = $configData.ollama_base_url
    $backendEnv.POSTGRES_HOST = $configData.postgres_host
    $backendEnv.POSTGRES_PORT = "$($configData.postgres_port)"
    $backendEnv.POSTGRES_DB = $configData.postgres_db
    $backendEnv.POSTGRES_USER = $configData.postgres_user
    $backendEnv.POSTGRES_PASSWORD = $configData.postgres_password
    $backendEnv.QDRANT_URL = $configData.qdrant_url
    $backendEnv.REDIS_URL = $configData.redis_url
    $backendEnv.MAX_UPLOAD_MB = "$($configData.max_upload_mb)"
    $backendEnv.GENERATION_TIMEOUT_SECONDS = "$($configData.generation_timeout_seconds)"
    $backendEnv.WORKER_CONCURRENCY = "$($configData.worker_concurrency)"

    Start-ServiceIfNeeded `
        -Name "FastAPI backend" `
        -Port $configData.backend_port `
        -Command @($conda, "run", "-n", $configData.conda_env_name, "python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$($configData.backend_port)", "--reload") `
        -LogPath $backendLog `
        -EnvVars $backendEnv

    $frontendEnv = ConvertTo-Hashtable $backendEnv
    $frontendEnv.BACKEND_URL = "http://localhost:$($configData.backend_port)"

    Start-ServiceIfNeeded `
        -Name "Streamlit frontend" `
        -Port $configData.frontend_port `
        -Command @($conda, "run", "-n", $configData.conda_env_name, "python", "-m", "streamlit", "run", "frontend/streamlit_app/app.py", "--server.port", "$($configData.frontend_port)") `
        -LogPath $frontendLog `
        -EnvVars $frontendEnv

    Write-Rule "Ready"
    Write-Host "$($C.Green)Backend $($C.Reset)  http://localhost:$($configData.backend_port)"
    Write-Host "$($C.Green)Frontend$($C.Reset)  http://localhost:$($configData.frontend_port)"
    Write-Host "$($C.Gray)Logs    $($C.Reset)  $logDir"
    Write-Host ""
    Write-Host "$($C.Dim)Run .\launch.ps1 -Config to change setup. Use -ConfigOnly to save without launching.$($C.Reset)"
    Write-Host ""

    if ($configData.open_browser) {
        Start-Process "http://localhost:$($configData.frontend_port)" | Out-Null
    }
} catch {
    Write-Rule "Launch failed"
    Fail $_.Exception.Message
    Write-Host ""
    Write-Host "$($C.Yellow)Useful checks:$($C.Reset)"
    Write-Host "  conda env list"
    Write-Host "  ollama list"
    Write-Host "  Get-Content '$ConfigPath'"
    Write-Host "  Get-Content '<storage-dir>\cache\logs\backend.log' -Tail 40"
    Write-Host "  Get-Content '<storage-dir>\cache\logs\frontend.log' -Tail 40"
    exit 1
}
