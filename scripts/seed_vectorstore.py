#!/usr/bin/env python3
"""Seed the vector store with initial data from all sources."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sync.scheduler import run_full_sync
from src.utils.logging import configure_logging, get_logger


def main() -> None:
    """Run a full sync to seed the vector store."""
    configure_logging()
    logger = get_logger(__name__)

    logger.info("starting_vectorstore_seed")

    try:
        results = run_full_sync()

        logger.info("seed_completed", results=results)
        print("\nSeed Results:")
        print("-" * 40)
        for source, count in results.items():
            print(f"  {source}: {count} documents")
        print("-" * 40)
        print(f"  Total: {sum(results.values())} documents")

    except Exception as e:
        logger.error("seed_failed", error=str(e))
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
