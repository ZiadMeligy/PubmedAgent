import asyncio
from typing import List, Dict, Any
import logging
from src.fulltext.europe_pmc import EuropePMCProvider
from src.fulltext.pmc import PMCProvider
from src.fulltext.unpaywall import UnpaywallProvider
from src.fulltext.crossref import CrossrefProvider

logger = logging.getLogger(__name__)

# Providers in priority order
PROVIDERS = [
    EuropePMCProvider(),
    PMCProvider(),
    UnpaywallProvider(),
    CrossrefProvider()
]

async def check_paper_availability(paper: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check availability for a single paper by trying providers in sequence.
    """
    pmid = paper.get("pmid") or paper.get("pubmed_id")
    result = {
        "pmid": pmid,
        "available": False,
        "pdf_url": None,
        "provider": None
    }
    
    # We still need the raw dict for the providers to extract pmid and doi
    provider_paper_arg = {
        "pubmed_id": pmid,
        "doi": paper.get("doi")
    }
    
    for provider in PROVIDERS:
        try:
            pdf_url = await provider.check_availability(provider_paper_arg)
            if pdf_url:
                result["available"] = True
                result["pdf_url"] = pdf_url
                result["provider"] = provider.name
                logger.info(f"Found PDF for PMID {pmid} via {provider.name}")
                break
        except Exception as e:
            logger.error(f"Error checking provider {provider.name} for PMID {pmid}: {e}")
            
    return result

async def check_multiple_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Check availability for multiple papers concurrently.
    """
    tasks = [check_paper_availability(paper) for paper in papers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any unexpected exceptions from gather (though they should be caught in check_paper_availability)
    final_results = []
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Unexpected error checking paper {papers[idx]}: {res}")
            pmid = papers[idx].get("pmid") or papers[idx].get("pubmed_id")
            final_results.append({
                "pmid": pmid,
                "available": False,
                "pdf_url": None,
                "provider": None
            })
        else:
            final_results.append(res)
            
    return final_results
