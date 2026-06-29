import httpx
from typing import Optional, Dict, Any
from src.fulltext.base import FullTextProvider
import logging

logger = logging.getLogger(__name__)

class EuropePMCProvider(FullTextProvider):
    @property
    def name(self) -> str:
        return "Europe PMC"
        
    async def check_availability(self, paper: Dict[str, Any]) -> Optional[str]:
        pmid = paper.get("pubmed_id")
        if not pmid or pmid == "N/A":
            return None
            
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=ext_id:{pmid}&format=json&resultType=core"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("resultList", {}).get("result", [])
                if not results:
                    return None
                    
                article = results[0]
                
                # Check for direct PDF URL in fullTextUrlList
                url_list = article.get("fullTextUrlList", {}).get("fullTextUrl", [])
                for item in url_list:
                    if item.get("documentStyle", "").lower() == "pdf":
                        return item.get("url")
                        
                # If no direct PDF URL but it's open access, maybe we can construct it if PMCID exists
                if article.get("isOpenAccess") == "Y":
                    pmcid = article.get("pmcid")
                    if pmcid:
                        return f"https://europepmc.org/articles/{pmcid}?pdf=render"
                        
        except Exception as e:
            logger.warning(f"Europe PMC error for PMID {pmid}: {e}")
            
        return None
