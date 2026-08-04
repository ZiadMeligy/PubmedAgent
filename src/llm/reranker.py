"""
Reranker for retrieved chunks using semantic similarity and relevance scoring.
"""

import logging
from typing import List, Dict, Optional
from src.embeddings import get_embeddings, compute_similarity
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_cross_encoder = None
_cross_encoder_unavailable = False


def _get_cross_encoder():
    """Load the cached biomedical-capable reranker lazily."""
    global _cross_encoder, _cross_encoder_unavailable
    if _cross_encoder is None and not _cross_encoder_unavailable:
        try:
            _cross_encoder = CrossEncoder(
                "BAAI/bge-reranker-base",
                local_files_only=True,
                max_length=512,
            )
        except Exception as exc:
            _cross_encoder_unavailable = True
            logger.warning("Cross-encoder unavailable; using embedding fallback: %s", exc)
    return _cross_encoder


def rerank_chunks(
    query: str,
    chunks: List[Dict],
    top_k: int = 6,
    selected_pmids: Optional[List[str]] = None,
) -> List[Dict]:
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
    
    chunk_texts = [chunk.get("text", "") for chunk in chunks]
    model = _get_cross_encoder()

    if model is not None:
        scores = model.predict(
            [(query, text) for text in chunk_texts],
            batch_size=16,
            show_progress_bar=False,
        )
    else:
        query_embedding = get_embeddings([query], use_instruction=True)[0]
        chunk_embeddings = get_embeddings(chunk_texts, use_instruction=False)
        scores = compute_similarity(query_embedding, chunk_embeddings)

    query_lower = query.lower()
    for index, chunk in enumerate(chunks):
        score = float(scores[index])
        content_type = chunk.get("content_type", "text")
        if content_type == "image" and any(
            term in query_lower for term in ("figure", "image", "plot", "graph", "chart")
        ):
            score += 0.75
        if content_type == "table" and any(
            term in query_lower for term in ("table", "compare", "comparison")
        ):
            score += 0.75
        chunk["rerank_score"] = score

    ranked = sorted(
        chunks,
        key=lambda item: item.get("rerank_score", float("-inf")),
        reverse=True,
    )

    if not selected_pmids:
        return ranked[:top_k]

    # Guarantee equal evidence capacity for each explicitly selected paper.
    balanced: List[Dict] = []
    for pmid in selected_pmids:
        paper_chunks = [
            chunk for chunk in ranked if str(chunk.get("pmid")) == str(pmid)
        ]
        balanced.extend(paper_chunks[:top_k])
    return balanced


def format_chunks_for_qa(chunks: List[Dict]) -> str:
    """
    Format reranked chunks for Q&A model context.
    Deduplicates sources to include paper metadata only once.
    
    Args:
        chunks: List of reranked chunks with metadata
    
    Returns:
        Formatted context string
    """
    if not chunks:
        return "No relevant information found."
    
    context = "RELEVANT PAPER EVIDENCE:\n"
    context += "=" * 80 + "\n\n"
    
    # Group by PMID
    papers = {}
    for chunk in chunks:
        pmid = chunk.get('pmid', 'Unknown')
        if pmid not in papers:
            papers[pmid] = {
                'title': chunk.get('title', 'Unknown'),
                'year': chunk.get('year', 'Unknown'),
                'journal': chunk.get('journal', 'Unknown'),
                'url': chunk.get('url') or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                'rank': chunk.get('rank'),
                'chunks': []
            }
        papers[pmid]['chunks'].append({
            'text': chunk.get('text', ''),
            'score': chunk.get('rerank_score', 0),
            'section': chunk.get('section') or 'Unknown',
            'content_type': chunk.get('content_type') or 'text',
            'artifact_url': chunk.get('artifact_url'),
        })
        
    for idx, (pmid, paper) in enumerate(papers.items(), 1):
        rank_label = paper.get("rank") or idx
        context += f"RANKED PAPER #{rank_label}:\n"
        context += f"TITLE:\n{paper['title']}\n\n"
        context += f"PMID:\n{pmid}\n\n"
        context += f"YEAR:\n{paper['year']}\n\n"
        context += f"JOURNAL:\n{paper['journal']}\n\n"
        context += f"URL:\n{paper['url']}\n\n"
        
        for i, chunk in enumerate(paper['chunks'], 1):
            context += (
                f"{chunk['content_type'].upper()} EVIDENCE "
                f"(Section: {chunk['section']}; Relevance: {chunk['score']:.4f}):\n"
            )
            context += f"{chunk['text']}\n\n"
            if chunk.get("artifact_url"):
                context += f"DISPLAYABLE ARTIFACT URL: {chunk['artifact_url']}\n\n"
            
        context += "-" * 80 + "\n\n"
    
    return context
