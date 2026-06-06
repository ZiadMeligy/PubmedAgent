"""
Reranker for retrieved chunks using semantic similarity and relevance scoring.
"""

from typing import List, Dict
from src.embeddings import get_embeddings, compute_similarity
import numpy as np


def rerank_chunks(query: str, chunks: List[Dict], top_k: int = 3) -> List[Dict]:
    """
    Rerank retrieved chunks by semantic similarity to query.
    
    Args:
        query: User's question
        chunks: List of chunks retrieved from vector store
        top_k: Number of top chunks to return
    
    Returns:
        Reranked chunks with scores
    """
    if not chunks:
        return []
    
    # Get embeddings
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    chunk_texts = [chunk['text'] for chunk in chunks]
    chunk_embeddings = get_embeddings(chunk_texts, use_instruction=False)
    
    # Compute similarities
    similarities = compute_similarity(query_embedding, chunk_embeddings)
    
    # Add similarity scores and sort
    for i, chunk in enumerate(chunks):
        chunk['rerank_score'] = float(similarities[i])
    
    # Sort by rerank score and keep top k
    reranked = sorted(chunks, key=lambda x: x['rerank_score'], reverse=True)[:top_k]
    
    return reranked


def format_chunks_for_qa(chunks: List[Dict]) -> str:
    """
    Format reranked chunks for Q&A model context.
    
    Args:
        chunks: List of reranked chunks with metadata
    
    Returns:
        Formatted context string
    """
    if not chunks:
        return "No relevant information found."
    
    context = "RELEVANT ABSTRACT CHUNKS:\n"
    context += "=" * 80 + "\n\n"
    
    for i, chunk in enumerate(chunks, 1):
        context += f"[Chunk {i}]\n"
        context += f"Paper: {chunk.get('title', 'Unknown')}\n"
        context += f"PMID: {chunk.get('pmid', 'Unknown')}\n"
        context += f"Section: {chunk.get('section', 'Unknown')}\n"
        context += f"Relevance Score: {chunk.get('rerank_score', 0):.4f}\n"
        context += f"\nText:\n{chunk['text']}\n\n"
        context += "-" * 80 + "\n\n"
    
    return context
