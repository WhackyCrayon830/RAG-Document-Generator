#!/bin/bash
# ============================================================
# RAG Platform - Linux Setup Script (Conda)
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "============================================================"
echo "  RAG Platform - Setup Script for Linux/macOS"
echo "============================================================"
echo ""

# 1. Check Conda
if ! command -v conda &> /dev/null; then
    error "Conda not found. Please install Miniconda or Anaconda first.\nDownload: https://docs.conda.io/en/latest/miniconda.html"
fi
info "Conda found: $(conda --version)"

# 2. Create Conda environment
info "Creating Conda environment 'rag_platform' (Python 3.11)..."
if conda env list | grep -q "^rag_platform "; then
    warn "Environment 'rag_platform' already exists. Updating..."
    conda env update -f environment.yml --prune
else
    conda env create -f environment.yml
fi
info "Conda environment ready."

# 3. Create required directories
info "Creating project directories..."
mkdir -p models vector_db uploads exports prompts config plugins
info "Directories created."

# 4. Copy .env template
if [ ! -f ".env" ]; then
    cp .env.template .env
    info ".env file created from template. Edit it to add your HuggingFace token."
else
    warn ".env already exists. Skipping."
fi

# 5. Validate installation
info "Validating installation..."
conda run -n rag_platform python -c "
import streamlit, sentence_transformers, faiss, fitz, docx, pandas, bs4, transformers
print('All core dependencies imported successfully.')
" || warn "Some dependencies may be missing. Check the error above."

echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "  To start the app:"
echo "    conda activate rag_platform"
echo "    streamlit run app.py"
echo ""
echo "  Or use the start script:"
echo "    bash start.sh"
echo ""
echo "  For online mode: add your HF token to .env"
echo "  For offline mode: download a model into models/<model_name>/"
echo "    Example:"
echo "    huggingface-cli download microsoft/Phi-3-mini-4k-instruct \\"
echo "      --local-dir models/Phi-3-mini-4k-instruct"
echo ""
