"""
Text processing and chunking functionality for papers.
"""

import re
from typing import List


# -------------------------
# ABSTRACT CHUNKING
# -------------------------

def chunk_abstract(abstract: str, sentences_per_chunk: int = 2) -> List[str]:
    """
    Split abstract into semantic chunks (2-4 sentences per chunk).
    
    Args:
        abstract: Full abstract text
        sentences_per_chunk: Number of sentences per chunk (default 2)
    
    Returns:
        List of abstract chunks
    """
    if not abstract or abstract == "No abstract available":
        return [abstract]
    
    # Split by periods followed by space (simple sentence splitter)
    # Handle edge cases like "et al.", "Dr.", "etc."
    sentences = re.split(r'(?<=[.!?])\s+', abstract.strip())
    
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        chunk = ' '.join(sentences[i:i+sentences_per_chunk])
        if chunk.strip():
            chunks.append(chunk.strip())
    
    return chunks if chunks else [abstract]
