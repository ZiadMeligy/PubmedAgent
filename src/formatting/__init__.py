"""
Output formatting utilities for papers and results.
"""

from typing import List, Dict


def format_ranked_papers(query: str, papers: List[Dict]) -> str:
    """
    Format ranked papers for display - minimal output with only key metrics.
    
    Args:
        query: Original search query
        papers: List of ranked papers with all scores
    
    Returns:
        Formatted string output with rank, score, citations, year, and URL
    """
    if not papers:
        return f"Query: {query}\n\nNo papers found."
    
    output = f"Query: {query}\n\n"
    output += "TOP 5 RANKED PAPERS\n"
    output += "=" * 80 + "\n\n"
    
    for rank, paper in enumerate(papers, 1):
        output += f"{rank}. {paper['title']}\n"
        output += f"   Composite Score: {paper['composite_score']:.4f}\n"
        output += f"   Citations: {paper['citation_count']}\n"
        output += f"   Year: {paper['publication_year'] if paper['publication_year'] else 'Unknown'}\n"
        output += f"   URL: {paper['url']}\n\n"
    
    return output
