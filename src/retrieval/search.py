"""
PubMed search and hierarchical ranking functionality.
"""

import logging
import json
import os
import re

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

logger = logging.getLogger(__name__)

# Load Journal SJR lookup at module level
_JOURNAL_SJR_LOOKUP = {}
try:
    sjr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "journal_sjr.json")
    with open(sjr_path, "r", encoding="utf-8") as f:
        _JOURNAL_SJR_LOOKUP = json.load(f)
except Exception as e:
    logger.warning(f"Could not load journal SJR lookup: {e}")

def normalize_journal_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


# -------------------------
# RETRIEVAL FUNCTIONS
# -------------------------

def search_pubmed(query: str, max_results: int = PUBMED_MAX_RESULTS) -> List[Dict]:
    """
    Search PubMed for medical research papers.
    
    Args:
        query: Search query string
        max_results: Number of papers to fetch
    
    Returns:
        List of paper dictionaries with metadata
    """
    pubmed = PubMed(tool="pubmed", email="your_email@example.com")
    results = list(pubmed.query(query, max_results=max_results))
    logger.info(f"Retrieved {len(results)} papers from PubMed for query: '{query}'")
    papers = []

    for article in results:
        logger.debug(f"{article.publication_date} {article.title}")
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
            
        issn = getattr(article, 'issn', None)
        
        # Extract DOI
        doi = None
        doi_raw = getattr(article, 'doi', None)
        if doi_raw and isinstance(doi_raw, str):
            doi = doi_raw.split()[0].strip()
        
        papers.append({
            "title": title,
            "abstract": abstract,
            "pubmed_id": pubmed_id,
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            "publication_year": publication_year,
            "citation_count": None,  # Will be filled later
            "journal": journal,
            "issn": issn,
        })

    return papers


def rank_titles(original_prompt: str, papers: List[Dict]) -> List[Dict]:
    """
    Stage 1: Rank papers by title similarity against the original clinical note.
    
    Args:
        original_prompt: User's original clinical note
        papers: List of paper dictionaries from search_pubmed
    
    Returns:
        Top 10 papers ranked by title similarity with scores
    """
    titles = [paper["title"] for paper in papers]
    
    # Get embeddings using the original prompt!
    query_embedding = get_embeddings([original_prompt], use_instruction=True)[0]
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
    original_prompt: str,
    papers: List[Dict],
    alpha: float,
    beta: float,
    gamma: float,
) -> List[Dict]:
    """
    Stage 2: Rank papers by abstract similarity using chunk-based retrieval.
    
    Also compute recency scores, citation scores, and weighted composite scores.
    
    Args:
        original_prompt: User's original clinical note
        papers: Top papers from title ranking
        alpha: Weight for semantic similarity (default 0.8)
        beta: Weight for recency (default 0.1)
        gamma: Weight for citations (default 0.1)
    
    Returns:
        Top 5 papers ranked by composite score
    """
    query_embedding = get_embeddings([original_prompt], use_instruction=True)[0]
    
    # Pre-fetch citation counts to find the maximum in the pool
    for paper in papers:
        paper["citation_count"] = get_citations_for_pmid(paper["pubmed_id"])
        
    # Calculate dynamic max citations for normalization
    max_citations = max([p["citation_count"] for p in papers if p["citation_count"] is not None] + [0])
    
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
        citation_count = paper["citation_count"]
        citation_score = compute_citation_score(citation_count, max_citations=max_citations)
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
    original_prompt: str,
    queries: Dict[str, str],
    alpha: float = SCORE_ALPHA,
    beta: float = SCORE_BETA,
    gamma: float = SCORE_GAMMA,
    journal_quality_enabled: bool = False,
    minimum_sjr: float = 10.0
) -> List[Dict]:
    """
    Execute hierarchical retrieval: multi-query fetch -> deduplicate -> title filtering -> abstract ranking.
    
    Args:
        original_prompt: The user's original clinical note for semantic embeddings
        queries: A dictionary of queries generated by the LLM
        alpha: Weight for semantic similarity
        beta: Weight for recency
        gamma: Weight for citations
    
    Returns:
        Top papers ranked by weighted composite score
    """
    print("\\n" + "="*52)
    print("Original Clinical Note")
    print(original_prompt)
    print("---")
    print("Generated Queries")
    for k, v in queries.items():
        print(f"{k.capitalize()}:\\n{v}")
    print("---")
    print("PubMed Results")
    
    all_papers = []
    # 1. Multi-query retrieval with explicit quotas
    # If we have 5 queries, we fetch ~20 papers each to get ~100 total
    papers_per_query = 20
    for query_type, q_string in queries.items():
        papers = search_pubmed(q_string, max_results=papers_per_query)
        print(f"{query_type.capitalize()}:\\n{len(papers)} papers")
        all_papers.extend(papers)
        
    print(f"\\nMerged:\\n{len(all_papers)}")
    
    # 2. Deduplicate by PMID
    seen_pmids = set()
    dedup_papers = []
    for p in all_papers:
        if p["pubmed_id"] not in seen_pmids:
            seen_pmids.add(p["pubmed_id"])
            dedup_papers.append(p)
            
    print(f"\\nDeduplicated:\\n{len(dedup_papers)}")
    
    if journal_quality_enabled:
        filtered_papers = []
        for p in dedup_papers:
            issn = p.get("issn")
            journal_name = p.get("journal", "")
            norm_journal = normalize_journal_name(journal_name)
            
            sjr_entry = None
            if issn and issn in _JOURNAL_SJR_LOOKUP:
                sjr_entry = _JOURNAL_SJR_LOOKUP[issn]
            elif norm_journal and norm_journal in _JOURNAL_SJR_LOOKUP:
                sjr_entry = _JOURNAL_SJR_LOOKUP[norm_journal]
                
            if sjr_entry and sjr_entry["sjr"] >= minimum_sjr:
                p["sjr"] = sjr_entry["sjr"]
                p["quartile"] = sjr_entry["quartile"]
                filtered_papers.append(p)
                
        print(f"Journal Quality Filter (>= {minimum_sjr}):\\nPassed: {len(filtered_papers)} / {len(dedup_papers)}")
        dedup_papers = filtered_papers

    print("---")
    
    if not dedup_papers:
        return []
    
    # Stage 1: Rank by titles (keep top 20 or PUBMED_TITLE_TOP_K)
    print("Ranking")
    print("Embedding Query:\\nOriginal clinical note")
    print(f"Ranking candidates:\\n{len(dedup_papers)}")
    
    papers = rank_titles(original_prompt, dedup_papers)
    
    # Stage 2: Rank top by abstracts with weighted scoring
    papers = rank_abstracts(original_prompt, papers, alpha=alpha, beta=beta, gamma=gamma)
    
    print(f"Top {len(papers)} selected")
    print("="*52 + "\\n")
    return papers
