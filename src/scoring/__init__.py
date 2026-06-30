"""
Scoring functions for paper ranking and evaluation.
"""

from datetime import datetime
import numpy as np
from src.config import RECENCY_DECAY_RATE, MAX_CITATIONS_REFERENCE


# -------------------------
# SCORING FUNCTIONS
# -------------------------

def compute_recency_score(publication_year: int) -> float:
    """
    Compute recency score normalized to [0, 1].
    
    Newer papers receive higher scores using exponential decay.
    
    Args:
        publication_year: Year of publication (e.g., 2024)
    
    Returns:
        Recency score in range [0, 1]
    """
    if publication_year is None:
        return 0.0
    
    current_year = datetime.now().year
    years_ago = max(0, current_year - publication_year)
    
    # Exponential decay: e^(-decay_rate * years_ago)
    # decay_rate = 0.15 means papers lose ~14% of recency per year
    decay_rate = RECENCY_DECAY_RATE
    recency = np.exp(-decay_rate * years_ago)
    
    return float(recency)


def compute_citation_score(citation_count: int, max_citations: int = MAX_CITATIONS_REFERENCE) -> float:
    """
    Compute citation score normalized to [0, 1] using log scaling.
    
    Args:
        citation_count: Number of citations
        max_citations: Maximum number of citations in the current candidate pool

    
    Returns:
        Citation score in range [0, 1]
    """
    if citation_count is None or citation_count <= 0:
        return 0.0
    
    # Log scale: log(1 + citations) normalized
    # Using log1p for better numerical stability
    log_citations = np.log1p(citation_count)
    
    # Normalize by assuming max citations from the pool
    # This puts highly cited papers (relative to the pool) near 1.0
    # Add 1 to avoid division by zero if max_citations is 0
    max_log = np.log1p(max(max_citations, 1))
    citation_score = min(1.0, log_citations / max_log)
    
    return float(citation_score)


def compute_composite_score(
    similarity_score: float,
    recency_score: float,
    citation_score: float,
    alpha: float,
    beta: float,
    gamma: float,
) -> float:
    """
    Compute weighted composite score with user-controlled parameters.
    
    Weights are automatically normalized to sum to 1.
    
    Args:
        similarity_score: Abstract semantic similarity [0, 1]
        recency_score: Publication recency [0, 1]
        citation_score: Citation impact [0, 1]
        alpha: Weight for similarity
        beta: Weight for recency
        gamma: Weight for citations
    
    Returns:
        Composite score in range [0, 1]
    """
    # Normalize weights
    total = alpha + beta + gamma
    if total == 0:
        # Handle edge case where all weights are 0
        total = 1.0
    
    alpha_norm = alpha / total
    beta_norm = beta / total
    gamma_norm = gamma / total
    
    # Compute weighted score
    composite = (
        alpha_norm * similarity_score +
        beta_norm * recency_score +
        gamma_norm * citation_score
    )
    
    return float(composite)
