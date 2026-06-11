#!/bin/bash
# Start the RAG Platform Streamlit app
echo "Starting RAG Platform..."

# Activate conda env if not already active
if [[ "$CONDA_DEFAULT_ENV" != "rag_platform" ]]; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate rag_platform
fi

streamlit run app.py \
    --server.port 8501 \
    --server.address localhost \
    --server.maxUploadSize 200 \
    --browser.gatherUsageStats false
