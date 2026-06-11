@echo off
REM ============================================================
REM  RAG Platform - Windows Setup Script (Conda)
REM ============================================================

echo ============================================================
echo   RAG Platform - Setup Script for Windows
echo ============================================================
echo.

REM 1. Check Conda
where conda >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Conda not found. Install Miniconda from:
    echo         https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)
echo [INFO] Conda found.

REM 2. Create Conda environment
echo [INFO] Creating Conda environment 'rag_platform'...
conda env list | findstr "rag_platform" >nul 2>&1
IF ERRORLEVEL 1 (
    conda env create -f environment.yml
) ELSE (
    echo [WARN] Environment already exists. Updating...
    conda env update -f environment.yml --prune
)
echo [INFO] Conda environment ready.

REM 3. Create required directories
echo [INFO] Creating project directories...
if not exist models mkdir models
if not exist vector_db mkdir vector_db
if not exist uploads mkdir uploads
if not exist exports mkdir exports
if not exist prompts mkdir prompts
if not exist config mkdir config
if not exist plugins mkdir plugins
echo [INFO] Directories created.

REM 4. Copy .env template
if not exist .env (
    copy .env.template .env
    echo [INFO] .env created from template. Add your HF token if using online mode.
) ELSE (
    echo [WARN] .env already exists. Skipping.
)

REM 5. Validate
echo [INFO] Validating installation...
conda run -n rag_platform python -c "import streamlit, sentence_transformers, faiss, fitz, docx, pandas, bs4, transformers; print('OK')"
IF ERRORLEVEL 1 (
    echo [WARN] Some imports failed. Check the errors above.
) ELSE (
    echo [INFO] All dependencies validated.
)

echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo   To start the app:
echo     conda activate rag_platform
echo     streamlit run app.py
echo.
echo   Or double-click start.bat
echo.
echo   For offline mode: place model folder in models\
echo   For online mode: add HF_TOKEN to .env
echo.
pause
