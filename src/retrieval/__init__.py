"""
Citation retrieval from OpenAlex and Semantic Scholar APIs.
"""

import requests
from typing import Optional, Dict


class PubMedCitationFinder:
    """Retrieve citation counts from OpenAlex and Semantic Scholar via DOI."""
    
    PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    OPENALEX_BASE = "https://api.openalex.org"
    SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 5

    def get_paper_info_from_pmid(self, pmid: str) -> dict:
        """Extract DOI from PubMed ID."""
        try:
            url = f"{self.PUBMED_BASE}/esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
            }
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()

            article = response.json()["result"][str(pmid)]

            doi = None
            for item in article.get("articleids", []):
                if item.get("idtype") == "doi":
                    doi = item["value"]
                    break

            if not doi:
                return None

            return {
                "pmid": pmid,
                "title": article.get("title"),
                "doi": doi,
            }
        except Exception:
            return None

    def get_openalex_metrics(self, doi: str) -> dict:
        """Get citation count from OpenAlex via DOI."""
        try:
            doi_clean = doi.lower().replace("https://doi.org/", "")
            url = f"{self.OPENALEX_BASE}/works/https://doi.org/{doi_clean}"
            response = self.session.get(url, timeout=5)

            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "openalex_citations": data.get("cited_by_count"),
            }
        except Exception:
            return None

    def get_semantic_scholar_metrics(self, doi: str) -> dict:
        """Get citation count from Semantic Scholar via DOI."""
        try:
            doi_clean = doi.lower().replace("https://doi.org/", "")
            url = f"{self.SEMANTIC_SCHOLAR_BASE}/paper/DOI:{doi_clean}"
            params = {"fields": "citationCount"}
            response = self.session.get(url, params=params, timeout=5)

            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "semantic_scholar_citations": data.get("citationCount"),
            }
        except Exception:
            return None

    def get_citations_for_pmid(self, pmid: str) -> int:
        """
        Get citation count for a paper using PMID.
        
        Returns the maximum citation count from available sources.
        """
        try:
            paper_info = self.get_paper_info_from_pmid(pmid)
            if not paper_info or not paper_info.get("doi"):
                return 0

            doi = paper_info["doi"]
            
            # Try OpenAlex first (usually more complete)
            openalex = self.get_openalex_metrics(doi) or {}
            openalex_citations = openalex.get("openalex_citations", 0) or 0
            
            # Try Semantic Scholar as backup
            semantic = self.get_semantic_scholar_metrics(doi) or {}
            semantic_citations = semantic.get("semantic_scholar_citations", 0) or 0
            
            # Return the maximum available
            return max(int(openalex_citations), int(semantic_citations))
        except Exception:
            return 0


# Initialize citation finder
_citation_finder = PubMedCitationFinder()


def get_citations_for_pmid(pubmed_id: str) -> int:
    """
    Retrieve citation count for a PubMed ID.
    
    Uses DOI lookup via OpenAlex and Semantic Scholar APIs.
    
    Args:
        pubmed_id: PubMed ID string
    
    Returns:
        Citation count (0 if unavailable)
    """
    if not pubmed_id or pubmed_id == "N/A":
        return 0
    
    return _citation_finder.get_citations_for_pmid(pubmed_id)
