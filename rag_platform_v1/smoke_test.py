#!/usr/bin/env python3
"""
Smoke test - verifies the full stack works (no model needed).
Run: python smoke_test.py

Tests:
  - Plugin discovery and loading
  - Text extraction from a sample file
  - Chunking
  - Embedding + FAISS indexing
  - Retrieval
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


def test(name, fn):
    try:
        fn()
        print(f"  {PASS} {name}")
        return True
    except Exception as e:
        print(f"  {FAIL} {name}: {e}")
        return False


def run_all():
    print("=" * 55)
    print("  RAG Platform - Smoke Test")
    print("=" * 55)
    results = []

    # 1. Plugin loading
    print("\n[1/6] Plugin Discovery")
    def t_plugins():
        from ingestion.plugin_registry import registry
        registry.discover_and_load()
        assert len(registry.supported_extensions()) >= 7, "Expected at least 7 extensions"
    results.append(test("Plugin auto-discovery", t_plugins))

    # 2. TXT extraction
    print("\n[2/6] Text Extraction (TXT plugin)")
    tmp_txt = None
    def t_txt():
        nonlocal tmp_txt
        from plugins.txt_plugin import TXTPlugin
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello world.\n\nThis is paragraph two.\n\nThird paragraph here.")
            tmp_txt = f.name
        plugin = TXTPlugin()
        chunks = plugin.extract(tmp_txt)
        assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
    results.append(test("TXT plugin extraction", t_txt))
    if tmp_txt:
        os.unlink(tmp_txt)

    # 3. Markdown extraction
    print("\n[3/6] Markdown Extraction")
    tmp_md = None
    def t_md():
        nonlocal tmp_md
        from plugins.markdown_plugin import MarkdownPlugin
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nSome text.\n\n## Section\n\n```python\nprint('hi')\n```\n")
            tmp_md = f.name
        plugin = MarkdownPlugin()
        chunks = plugin.extract(tmp_md)
        types = [c.chunk_type for c in chunks]
        assert "heading" in types, "Missing heading chunk"
        assert "code" in types, "Missing code chunk"
    results.append(test("Markdown plugin extraction", t_md))
    if tmp_md:
        os.unlink(tmp_md)

    # 4. Chunker
    print("\n[4/6] Chunker")
    def t_chunker():
        from ingestion.chunker import Chunker
        from plugins.base_plugin import DocumentChunk
        chunker = Chunker(chunk_size=50, chunk_overlap=5)
        big_text = "word " * 200
        raw = [DocumentChunk(text=big_text, source="test.txt", page=0, chunk_type="text")]
        result = chunker.chunk(raw)
        assert len(result) > 1, f"Expected multiple chunks, got {len(result)}"
    results.append(test("Chunker splits oversized text", t_chunker))

    # 5. Hardware detection
    print("\n[5/6] Hardware Detection")
    def t_hw():
        from services.hardware_detector import get_hardware_info
        hw = get_hardware_info()
        assert hw.device in ("cpu", "cuda"), f"Unknown device: {hw.device}"
        assert hw.cpu_cores > 0
    results.append(test("Hardware detection", t_hw))

    # 6. Vector store (requires sentence-transformers + faiss)
    print("\n[6/6] Embedding + FAISS")
    def t_vs():
        from plugins.base_plugin import DocumentChunk
        from retrieval.vector_store import VectorStore
        vs = VectorStore(embedding_model_name="sentence-transformers/all-MiniLM-L6-v2")
        chunks = [
            DocumentChunk(text="The pump motor overheats at high RPM.", source="manual.pdf", page=1, chunk_type="text"),
            DocumentChunk(text="Check the coolant level before starting.", source="manual.pdf", page=2, chunk_type="text"),
            DocumentChunk(text="Lubricate bearings every 500 hours.", source="sop.txt", page=0, chunk_type="text"),
        ]
        vs.add_chunks(chunks)
        results_search = vs.search("motor temperature problem", top_k=2)
        assert len(results_search) > 0, "No search results"
        assert results_search[0][0]["text"], "Empty result text"
    results.append(test("Embedding + FAISS search", t_vs))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*55}")
    print(f"  Results: {passed}/{total} passed")
    if passed == total:
        print(f"  {PASS} All tests passed! The platform is ready.")
    else:
        print(f"  {WARN} Some tests failed. Check dependency installation.")
        print("    Run: pip install -r requirements.txt")
    print("=" * 55)
    return passed == total


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
