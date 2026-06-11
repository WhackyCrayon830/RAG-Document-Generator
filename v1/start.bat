@echo off
echo Starting RAG Platform...
call conda activate rag_platform
streamlit run app.py --server.port 8501 --server.maxUploadSize 200 --browser.gatherUsageStats false
pause
