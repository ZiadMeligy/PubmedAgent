import httpx
from typing import Optional, Dict, Any
from src.fulltext.base import FullTextProvider
import logging

logger = logging.getLogger(__name__)

class CrossrefProvider(FullTextProvider):
    @property
    def name(self) -> str:
        return "Crossref"
        
    async def check_availability(self, paper: Dict[str, Any]) -> Optional[str]:
        doi = paper.get("doi")
        if not doi:
            return None
            
        url = f"https://api.crossref.org/works/{doi}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                
                message = data.get("message", {})
                links = message.get("link", [])
                
                for link in links:
                    if link.get("content-type", "").lower() == "application/pdf":
                        return link.get("URL")
                        
        except Exception as e:
            logger.warning(f"Crossref error for DOI {doi}: {e}")
            
        return None
