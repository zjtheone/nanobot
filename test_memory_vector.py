#!/usr/bin/env python3
"""Test vector memory adapter."""

import sys
sys.path.insert(0, '.')

from nanobot.agent.memory_vector import VectorMemoryAdapter
from pathlib import Path
import tempfile
import shutil

def main():
    workspace = Path(tempfile.mkdtemp())
    config = {
        "enabled": True,
        "storage_path": str(workspace / "memory.db"),
        "openai_api_key": "",
        "gemini_api_key": "",
        "embedding_fallback_chain": ["sentence_transformer"],
    }
    adapter = VectorMemoryAdapter(workspace, config)
    print(f"Adapter enabled: {adapter.enabled}")
    if adapter.enabled:
        print("Initializing...")
        # Sync full
        adapter.sync(full=True)
        # Search
        results = adapter.search("test query", limit=2)
        print(f"Search results: {results}")
    shutil.rmtree(workspace)

if __name__ == "__main__":
    main()