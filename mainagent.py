"""
Biomedical Literature Retrieval Agent - Root Entry Point

This module provides backward compatibility and serves as the main entry point
for running the modular biomedical literature retrieval agent.

The core functionality is organized in the src/ directory with specialized modules:
    src/config/      - Configuration and settings
    src/embeddings/  - Embedding models and functions
    src/scoring/     - Paper ranking and scoring
    src/retrieval/   - PubMed search and citation retrieval
    src/processing/  - Text chunking and processing
    src/storage/     - Vector database integration
    src/llm/        - Language model setup and prompts
    src/graph/      - LangGraph workflow and orchestration
    src/formatting/  - Output formatting utilities
"""

from src.mainagent import main

if __name__ == "__main__":
    main()
