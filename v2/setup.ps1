param(
    [switch]$Force,
    [switch]$Test,
    [switch]$SkipVenvCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($PSStyle) {
    $PSStyle.OutputRendering = "Ansi"
}

# ANSI Color codes matching launch.ps1
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

# =================== UTILITY FUNCTIONS ===================

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
    Write-Host "$($C.Bold)$($C.Cyan)|$($C.Reset) $($C.Bold)$($C.White)Offline RAG Document Generator$($C.Reset) $($C.Dim)$($C.White)- setup utility$($C.Reset)                          $($C.Bold)$($C.Cyan)|$($C.Reset)"
    Write-Host "$($C.Bold)$($C.Cyan)+--------------------------------------------------------------------------+$($C.Reset)"
    Write-Host ""
}

function Step { param([string]$Text) Write-Host "$($C.Blue)>$($C.Reset) $($C.Bold)$Text$($C.Reset)" }
function Ok { param([string]$Text) Write-Host "  $($C.Green)OK$($C.Reset)  $Text" }
function Warn { param([string]$Text) Write-Host "  $($C.Yellow)!!$($C.Reset)  $Text" }
function Fail { param([string]$Text) Write-Host "  $($C.Red)XX$($C.Reset)  $Text" }
function Info { param([string]$Text) Write-Host "  $($C.Cyan)ℹ$($C.Reset)  $Text" }

function Write-Section {
    param([string]$Title, [string]$Description = "")
    Write-Host ""
    Write-Host "$($C.Bold)$($C.Green)▶ $Title$($C.Reset)"
    if ($Description) {
        Write-Host "$($C.Dim)  $Description$($C.Reset)"
    }
}

function Test-Python {
    try {
        $output = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true, $output
        }
        return $false, "Python not found"
    } catch {
        return $false, "Error checking Python: $_"
    }
}

function Test-Conda {
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) { 
        return $true, $cmd.Source 
    }
    
    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe"
    )
    
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { 
            return $true, $candidate 
        }
    }
    return $false, "Conda not found"
}

function Test-CommandExists {
    param([string]$Command)
    try {
        $cmd = Get-Command $Command -ErrorAction SilentlyContinue
        return $null -ne $cmd
    } catch {
        return $false
    }
}

function Get-Ollama {
    try {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    } catch { }
    
    $candidates = @(
        "C:\Program Files\Ollama\ollama.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Ollama\ollama.exe"
    )
    
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Test-Docker {
    try {
        $output = docker --version 2>&1
        return ($LASTEXITCODE -eq 0), $output
    } catch {
        return $false, "Docker not found"
    }
}

function Install-Requirements {
    Step "Installing Python dependencies"
    $reqFile = Join-Path $PSScriptRoot "requirements.txt"
    
    if (-not (Test-Path $reqFile)) {
        Fail "requirements.txt not found at $reqFile"
        throw "Missing requirements.txt"
    }
    
    # Prefer installing inside the conda environment if available
    $condaOk, $condaPath = Test-Conda
    $envName = "rag_document_generator"
    if ($condaOk) {
        & $condaPath run -n $envName pip install --upgrade pip setuptools wheel
        & $condaPath run -n $envName pip install -r $reqFile
    } else {
        python -m pip install --upgrade pip
        python -m pip install -r $reqFile
    }
    
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to install some requirements"
        Warn "Check the output above and install missing packages manually"
    } else {
        Ok "Dependencies installed"
    }
}

function Test-ImportPackages {
    Step "Testing package imports"
    
    $packages = @(
        @{Module="fastapi"; Label="fastapi"},
        @{Module="streamlit"; Label="streamlit"},
        @{Module="pydantic"; Label="pydantic"},
        @{Module="redis"; Label="redis"},
        @{Module="qdrant_client"; Label="qdrant_client"},
        @{Module="celery"; Label="celery"},
        @{Module="reportlab"; Label="reportlab"},
        @{Module="pypdf"; Label="pypdf"},
        @{Module="docx"; Label="python-docx"},
        @{Module="pdfplumber"; Label="pdfplumber"},
        @{Module="pytesseract"; Label="pytesseract"},
        @{Module="numpy"; Label="numpy"},
        @{Module="pandas"; Label="pandas"}
    )
    
    # PyMuPDF can be imported as 'fitz' (old) or 'pymupdf' (new)
    $result = python -c "import fitz; print('pymupdf OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Ok "pymupdf (fitz) is importable"
    } else {
        Warn "pymupdf import failed – run: pip install pymupdf"
    }
    
    foreach ($pkg in $packages) {
        $result = python -c "import $($pkg.Module); print('$($pkg.Module) OK')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok "$($pkg.Label) is importable"
        } else {
            Warn "$($pkg.Label) import failed (may need installation)"
        }
    }
    
    # transformers is optional/large – just check without failing
    $result = python -c "import transformers; print('transformers OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Ok "transformers is importable (ML features enabled)"
    } else {
        Write-Host "  $($C.Dim)transformers not installed (optional – image captioning disabled)$($C.Reset)"
    }
}

function Verify-ProjectStructure {
    Step "Verifying project structure"
    
    $requiredDirs = @(
        "backend",
        "frontend",
        "storage",
        "scripts",
        "tests"
    )
    
    $requiredFiles = @(
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "docker-compose.yml",
        "launch.ps1"
    )
    
    $root = $PSScriptRoot
    
    foreach ($dir in $requiredDirs) {
        $path = Join-Path $root $dir
        if (Test-Path $path) {
            Ok "Found directory: $dir"
        } else {
            Warn "Missing directory: $dir"
        }
    }
    
    foreach ($file in $requiredFiles) {
        $path = Join-Path $root $file
        if (Test-Path $path) {
            Ok "Found file: $file"
        } else {
            Warn "Missing file: $file"
        }
    }
}

function Run-Tests {
    Step "Running test suite"
    
    if (-not (Test-CommandExists pytest)) {
        Warn "pytest not installed, skipping tests"
        return
    }
    
    Write-Host ""
    pytest tests/ -v --tb=short
    
    if ($LASTEXITCODE -eq 0) {
        Ok "All tests passed!"
    } else {
        Warn "Some tests failed (see output above)"
    }
}

function Show-Requirements {
    Write-Rule "System Requirements"
    Write-Host ""
    Write-Host "$($C.Bold)$($C.White)Required:$($C.Reset)"
    Write-Host "  • Python 3.9 or higher"
    Write-Host "  • Conda (Miniconda or Anaconda)"
    Write-Host "  • Docker & Docker Compose (for services)"
    Write-Host ""
    Write-Host "$($C.Bold)$($C.White)Optional but recommended:$($C.Reset)"
    Write-Host "  • Ollama (for local LLM inference)"
    Write-Host "  • PostgreSQL (or use Docker)"
    Write-Host "  • Redis (or use Docker)"
    Write-Host "  • Git (for version control)"
    Write-Host ""
}

function Show-Summary {
    param($FoundPython, $PythonVersion, $FoundConda, $CondaPath, $FoundOllama, $OllamaPath, $FoundDocker, $DockerVersion)
    
    Write-Rule "System Status Summary"
    Write-Host ""
    
    Write-Host "$($C.Bold)Environment$($C.Reset)"
    Write-Host "  Hostname   $($C.Cyan)$(hostname)$($C.Reset)"
    Write-Host "  User       $($C.Cyan)$env:USERNAME$($C.Reset)"
    Write-Host "  OS         $($C.Cyan)Windows$($C.Reset)"
    Write-Host "  Shell      $($C.Cyan)PowerShell $($PSVersionTable.PSVersion.Major).$($PSVersionTable.PSVersion.Minor)$($C.Reset)"
    Write-Host ""
    
    Write-Host "$($C.Bold)Tools$($C.Reset)"
    
    if ($FoundPython) {
        Write-Host "  Python     $($C.Green)✓$($C.Reset)  $PythonVersion"
    } else {
        Write-Host "  Python     $($C.Red)✗$($C.Reset)  Not found"
    }
    
    if ($FoundConda) {
        Write-Host "  Conda      $($C.Green)✓$($C.Reset)  $CondaPath"
    } else {
        Write-Host "  Conda      $($C.Red)✗$($C.Reset)  Not found"
    }
    
    if ($FoundOllama) {
        Write-Host "  Ollama     $($C.Green)✓$($C.Reset)  $OllamaPath"
    } else {
        Write-Host "  Ollama     $($C.Yellow)!$($C.Reset)  Not found (optional)"
    }
    
    if ($FoundDocker) {
        Write-Host "  Docker     $($C.Green)✓$($C.Reset)  $DockerVersion"
    } else {
        Write-Host "  Docker     $($C.Yellow)!$($C.Reset)  Not found (optional)"
    }
    
    Write-Host ""
}

# =================== MAIN EXECUTION ===================

try {
    Write-Logo
    Show-Requirements
    
    Write-Rule "Checking system configuration"
    Write-Host ""
    
    # Check Python
    Step "Checking Python installation"
    $pythonOk, $pythonVersion = Test-Python
    if ($pythonOk) {
        Ok "$pythonVersion"
    } else {
        Fail $pythonVersion
        if (-not $Force) {
            throw "Python is required to proceed"
        }
    }
    
    # Check Conda
    Step "Checking Conda installation"
    $condaOk, $condaPath = Test-Conda
    if ($condaOk) {
        Ok "Found: $condaPath"
    } else {
        Fail $condaPath
        if (-not $Force) {
            throw "Conda is required. Install Miniconda from https://docs.conda.io/en/latest/miniconda.html"
        }
    }
    
    # Check Ollama
    Step "Checking Ollama installation"
    $ollamaPath = Get-Ollama
    if ($ollamaPath) {
        Ok "Found: $ollamaPath"
    } else {
        Warn "Ollama not found (optional but recommended)"
        Info "Install from https://ollama.ai"
    }
    
    # Check Docker
    Step "Checking Docker installation"
    $dockerOk, $dockerVersion = Test-Docker
    if ($dockerOk) {
        Ok "$dockerVersion"
    } else {
        Warn "Docker not found (optional but recommended for services)"
        Info "Install from https://www.docker.com/products/docker-desktop"
    }
    
    # Verify project structure
    Write-Rule "Project validation"
    Verify-ProjectStructure
    
    # Show summary
    Write-Host ""
    Show-Summary -FoundPython $pythonOk -PythonVersion $pythonVersion -FoundConda $condaOk -CondaPath $condaPath -FoundOllama ($null -ne $ollamaPath) -OllamaPath $ollamaPath -FoundDocker $dockerOk -DockerVersion $dockerVersion
    
    # Optional: Install dependencies
    Write-Section "Dependencies" "Install Python packages"
    
    $installDeps = Read-Host "Install Python dependencies now? (y/n)"
    if ($installDeps -match "^(y|yes|Y|YES)$") {
        Install-Requirements
    } else {
        Info "Skipping dependency installation"
        Info "Run: python -m pip install -r requirements.txt"
    }
    
    # Optional: Test imports
    $testImports = Read-Host "Test package imports? (y/n)"
    if ($testImports -match "^(y|yes|Y|YES)$") {
        Test-ImportPackages
    }
    
    # Optional: Run tests
    if (-not $SkipVenvCheck) {
        $runTests = Read-Host "Run test suite? (y/n)"
        if ($runTests -match "^(y|yes|Y|YES)$") {
            Run-Tests
        }
    }
    
    # Final instructions
    Write-Rule "Next Steps"
    Write-Host ""
    Write-Host "$($C.Green)1. Configure the environment$($C.Reset)"
    Write-Host "   Run: .\launch.ps1 --config"
    Write-Host ""
    Write-Host "$($C.Green)2. Start the application$($C.Reset)"
    Write-Host "   Run: .\launch.ps1"
    Write-Host ""
    Write-Host "$($C.Green)3. View logs$($C.Reset)"
    Write-Host "   Backend:  storage/cache/logs/backend.log"
    Write-Host "   Frontend: storage/cache/logs/frontend.log"
    Write-Host ""
    Write-Host "$($C.Dim)For more information, see README.md$($C.Reset)"
    Write-Host ""
    
    Ok "Setup complete!"
    
} catch {
    Write-Rule "Setup failed"
    Fail $_.Exception.Message
    Write-Host ""
    Write-Host "$($C.Yellow)Troubleshooting:$($C.Reset)"
    Write-Host "  1. Install Python from python.org"
    Write-Host "  2. Install Conda from https://docs.conda.io/en/latest/miniconda.html"
    Write-Host "  3. Run again with -Force to skip validation"
    Write-Host "  4. Check README.md for detailed setup instructions"
    Write-Host ""
    exit 1
}
