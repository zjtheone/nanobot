#!/usr/bin/env python3
"""Integration test for vector memory adapter."""

import sys
import tempfile
import shutil
import asyncio
from pathlib import Path

sys.path.insert(0, '.')

from nanobot.agent.memory_vector import VectorMemoryAdapter

async def amain():
    workspace = Path(tempfile.mkdtemp())
    memory_dir = workspace / "memory"
    memory_dir.mkdir()
    
    # Create sample memory files
    memory_file = memory_dir / "MEMORY.md"
    memory_file.write_text("""
# Long-term Memory

## User Information
- User preferred name: Jian

## Preferences
- Communication style: casual
- Language: English
- Timezone: Asia/Shanghai

## Important Notes
- Assistant preferred name: Lee

## Projects
- Linux 1.0 Analysis: Started 2026-02-28, analyzing kernel source code.
""")
    
    history_file = memory_dir / "HISTORY.md"
    history_file.write_text("""
[2026-02-28 10:00] USER: Let's start the Linux 1.0 analysis project.
[2026-02-28 10:15] ASSISTANT: Created project structure and README.
[2026-02-28 11:00] USER: Need to add memory vector search to Nanobot.
[2026-02-28 11:30] ASSISTANT: Started implementing VectorMemoryAdapter.
[2026-02-28 13:00] USER: Let's enhance the hybrid search with a query parser.
[2026-02-28 14:00] ASSISTANT: Added QueryParser to identify keywords and phrases.
""")
    
    # Run tests with different configurations
    print("--- Test 1: Standard search ---")
    await run_test_with_config(workspace, {
        "enabled": True,
        "storage_path": str(workspace / "vector_memory_1.db"),
        "watch_paths": [],
        "max_distance": 0.4,
        "hybrid_weight": 0.5,
        "top_k": 10,
        "use_embedding_fallback": True,
        "embedding_provider": "sentence_transformer",
        "embedding_fallback_chain": ["sentence_transformer"],
        "query_parser_enabled": False,  # Disabled
    })
    
    print("\n--- Test 2: Enhanced search with query parsing ---")
    await run_test_with_config(workspace, {
        "enabled": True,
        "storage_path": str(workspace / "vector_memory_2.db"),
        "watch_paths": [],
        "max_distance": 0.4,
        "hybrid_weight": 0.5,
        "top_k": 10,
        "use_embedding_fallback": True,
        "embedding_provider": "sentence_transformer",
        "embedding_fallback_chain": ["sentence_transformer"],
        "query_parser_enabled": True,   # Enabled
    })
    
    shutil.rmtree(workspace)
    print("\nAll integration tests completed.")

async def run_test_with_config(workspace, config):
    adapter = VectorMemoryAdapter(workspace, config)
    print(f"Adapter enabled: {adapter.enabled}, Query Parser: {config.get('query_parser_enabled')}")
    if adapter.enabled:
        print("Performing full sync...")
        success = adapter.sync(full=True)
        print(f"Sync success: {success}")
        
        # Test 1: Vector matching 
        print("\nSearching for 'Linux kernel'...")
        results = await adapter.search("Linux kernel", limit=3)
        for i, r in enumerate(results):
            print(f"  {i+1}: {r.get('chunk', {}).get('text', '')[:100].replace('\n', ' ')}... (score: {r.get('score', 0):.3f})")
        
        # Test 2: Keyword priority (should find "QueryParser" easily)
        print("\nSearching for 'what is QueryParser'...")
        results = await adapter.search("what is QueryParser", limit=3)
        for i, r in enumerate(results):
            print(f"  {i+1}: {r.get('chunk', {}).get('text', '')[:100].replace('\n', ' ')}... (score: {r.get('score', 0):.3f})")
            
        # Test 3: Phrase matching (if parser is enabled, exact phrase should boost)
        print('\nSearching for phrase: "memory vector search"')
        results = await adapter.search('"memory vector search"', limit=3)
        for i, r in enumerate(results):
            print(f"  {i+1}: {r.get('chunk', {}).get('text', '')[:100].replace('\n', ' ')}... (score: {r.get('score', 0):.3f})")

def main():
    asyncio.run(amain())

if __name__ == "__main__":
    main()
