#!/usr/bin/env python3
"""
Rebuild the FAISS vector index from a folder of documents.
Run: python rebuild_index.py --folder /path/to/docs
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.ingestion_engine import IngestionEngine
from retrieval.vector_store import VectorStore


def main():
    parser = argparse.ArgumentParser(description="Rebuild vector index from documents")
    parser.add_argument("--folder", default="uploads", help="Folder containing documents")
    parser.add_argument("--embedding", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=64)
    args = parser.parse_args()

    print(f"Rebuilding index from: {args.folder}")
    print(f"Embedding model: {args.embedding}")

    engine = IngestionEngine(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)

    def progress(msg):
        print(f"  {msg}")

    chunks = engine.ingest_folder(args.folder, progress_cb=progress)
    print(f"\nExtracted {len(chunks)} chunks total.")

    if not chunks:
        print("No chunks found. Check the folder and supported file types.")
        return

    vs = VectorStore(embedding_model_name=args.embedding)
    vs.rebuild(chunks, progress_cb=progress)
    vs.save()
    print(f"\n✅ Index rebuilt with {vs.chunk_count} chunks.")
    print("Run the app: streamlit run app.py")


if __name__ == "__main__":
    main()
