"""
PubMed search and hierarchical ranking functionality.
"""

from typing import List, Dict
import numpy as np
from pymed import PubMed
from src.embeddings import get_embeddings, compute_similarity
from src.scoring import compute_recency_score, compute_citation_score, compute_composite_score
from src.retrieval import get_citations_for_pmid
from src.processing import chunk_abstract
from src.config import (
    PUBMED_MAX_RESULTS,
    PUBMED_TITLE_TOP_K,
    PUBMED_ABSTRACT_TOP_K,
    SCORE_ALPHA,
    SCORE_BETA,
    SCORE_GAMMA
)


# -------------------------
# RETRIEVAL FUNCTIONS
# -------------------------

def search_pubmed(query: str) -> List[Dict]:
    """
    Search PubMed for medical research papers.
    
    Args:
        query: Search query string
    
    Returns:
        List of paper dictionaries with metadata
    """
    pubmed = PubMed(tool="pubmed", email="your_email@example.com")
    results = list(pubmed.query(query, max_results=PUBMED_MAX_RESULTS))
    print(f"Retrieved {len(results)} papers from PubMed for query: '{query}'")
    papers = []

    for article in results:
        print(article.publication_date, article.title)
        title = article.title or "No title"
        abstract = article.abstract or "No abstract available"
        
        # Extract only the first PubMed ID (some fields contain multiple IDs)
        pubmed_id_raw = article.pubmed_id or "N/A"
        pubmed_id = pubmed_id_raw.split()[0] if pubmed_id_raw != "N/A" else "N/A"
        
        # Extract publication year
        publication_year = None
        if hasattr(article, 'publication_date') and article.publication_date:
            try:
                # publication_date is typically a datetime object or string
                if isinstance(article.publication_date, str):
                    publication_year = int(article.publication_date.split('-')[0]) if article.publication_date else None
                else:
                    publication_year = article.publication_date.year if hasattr(article.publication_date, 'year') else None
            except (ValueError, AttributeError):
                publication_year = None
        
        # Extract journal name
        journal = "Unknown"
        if hasattr(article, 'journal') and article.journal:
            journal = article.journal
        
        papers.append({
            "title": title,
            "abstract": abstract,
            "pubmed_id": pubmed_id,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            "publication_year": publication_year,
            "citation_count": None,  # Will be filled later
            "journal": journal,
        })

    return papers


def rank_titles(query: str, papers: List[Dict]) -> List[Dict]:
    """
    Stage 1: Rank papers by title similarity.
    
    Args:
        query: User's search query
        papers: List of paper dictionaries from search_pubmed
    
    Returns:
        Top 10 papers ranked by title similarity with scores
    """
    titles = [paper["title"] for paper in papers]
    
    # Get embeddings
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    title_embeddings = get_embeddings(titles, use_instruction=False)
    
    # Compute similarities
    title_similarities = compute_similarity(query_embedding, title_embeddings)
    
    # Add similarity scores and sort
    for i, paper in enumerate(papers):
        paper["title_similarity"] = float(title_similarities[i])
    
    # Sort by title similarity and keep top N
    ranked_papers = sorted(papers, key=lambda x: x["title_similarity"], reverse=True)[:PUBMED_TITLE_TOP_K]
    
    return ranked_papers


def rank_abstracts(
    query: str,
    papers: List[Dict],
    alpha: float,
    beta: float,
    gamma: float,
) -> List[Dict]:
    """
    Stage 2: Rank papers by abstract similarity using chunk-based retrieval.
    
    Also compute recency scores, citation scores, and weighted composite scores.
    
    Args:
        query: User's search query
        papers: Top 10 papers from title ranking
        alpha: Weight for semantic similarity (default 0.8)
        beta: Weight for recency (default 0.1)
        gamma: Weight for citations (default 0.1)
    
    Returns:
        Top 5 papers ranked by composite score
    """
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    
    # Process each paper
    for paper in papers:
        # --- ABSTRACT CHUNKING AND SIMILARITY ---
        abstract = paper["abstract"]
        chunks = chunk_abstract(abstract)
        
        # Embed all chunks
        chunk_embeddings = get_embeddings(chunks, use_instruction=False)
        
        # Compute similarities for each chunk
        chunk_similarities = compute_similarity(query_embedding, chunk_embeddings)
        
        # Use maximum chunk similarity as the paper's abstract score
        abstract_similarity = float(np.max(chunk_similarities)) if len(chunk_similarities) > 0 else 0.0
        paper["abstract_similarity"] = abstract_similarity
        
        # --- RECENCY SCORE ---
        recency_score = compute_recency_score(paper["publication_year"])
        paper["recency_score"] = recency_score
        
        # --- CITATION COUNT AND CITATION SCORE ---
        citation_count = get_citations_for_pmid(paper["pubmed_id"])
        paper["citation_count"] = citation_count
        citation_score = compute_citation_score(citation_count)
        paper["citation_score"] = citation_score
        
        # --- WEIGHTED COMPOSITE SCORE ---
        composite_score = compute_composite_score(
            similarity_score=abstract_similarity,
            recency_score=recency_score,
            citation_score=citation_score,
            alpha=alpha,
            beta=beta,
            gamma=gamma
        )
        paper["composite_score"] = composite_score
        
        # Store weights for output
        paper["alpha"] = alpha
        paper["beta"] = beta
        paper["gamma"] = gamma
    
    # Sort by composite score and keep top 5
    ranked_papers = sorted(papers, key=lambda x: x["composite_score"], reverse=True)[:PUBMED_ABSTRACT_TOP_K]
    
    return ranked_papers


def hierarchical_retrieve(
    query: str,
    alpha: float = SCORE_ALPHA,
    beta: float = SCORE_BETA,
    gamma: float = SCORE_GAMMA
) -> List[Dict]:
    """
    Execute hierarchical retrieval: title filtering -> abstract ranking.
    
    Args:
        query: User's search query
        alpha: Weight for semantic similarity
        beta: Weight for recency
        gamma: Weight for citations
    
    Returns:
        Top 5 papers ranked by weighted composite score
    """
    # Stage 1: Retrieve up to 20 papers and rank by titles (keep top 10)
    papers = search_pubmed(query)
    if not papers:
        return []
    
    papers = rank_titles(query, papers)
    
    # Stage 2: Rank top 10 by abstracts (keep top 5) with weighted scoring
    papers = rank_abstracts(query, papers, alpha=alpha, beta=beta, gamma=gamma)
    
    return papers
