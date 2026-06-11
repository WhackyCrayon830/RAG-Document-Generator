#!/usr/bin/env python3
"""
Validate all plugins are correctly installed and functional.
Run: python validate_plugins.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.plugin_registry import registry

print("=" * 50)
print("RAG Platform - Plugin Validation")
print("=" * 50)

registry.discover_and_load()

supported = registry.supported_extensions()
errors = registry.get_load_errors()
loaded = registry.get_loaded_plugins()

print(f"\n✅ Loaded plugins: {len(loaded)}")
for p in loaded:
    print(f"   - {p}")

print(f"\n📂 Supported extensions: {supported}")

if errors:
    print(f"\n❌ Plugin load errors ({len(errors)}):")
    for name, err in errors.items():
        print(f"   {name}: {err}")
else:
    print("\n✅ No plugin errors.")

print("\n" + "=" * 50)
print("Validation complete.")
