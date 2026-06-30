import httpx
from typing import Optional, Dict, Any
from src.fulltext.base import FullTextProvider
import logging

logger = logging.getLogger(__name__)

class PMCProvider(FullTextProvider):
    @property
    def name(self) -> str:
        return "PubMed Central"
        
    async def check_availability(self, paper: Dict[str, Any]) -> Optional[str]:
        pmid = paper.get("pubmed_id")
        if not pmid or pmid == "N/A":
            return None
            
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                records = data.get("records", [])
                if not records:
                    return None
                    
                record = records[0]
                pmcid = record.get("pmcid")
                
                if pmcid:
                    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                    
        except Exception as e:
            logger.warning(f"PMC error for PMID {pmid}: {e}")
            
        return None
