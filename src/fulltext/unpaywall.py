import httpx
from typing import Optional, Dict, Any
from src.fulltext.base import FullTextProvider
import logging

logger = logging.getLogger(__name__)

class UnpaywallProvider(FullTextProvider):
    @property
    def name(self) -> str:
        return "Unpaywall"
        
    async def check_availability(self, paper: Dict[str, Any]) -> Optional[str]:
        doi = paper.get("doi")
        if not doi:
            return None
            
        # Unpaywall requires a valid-looking email parameter (they block example.com domains).
        email = "hello@pubmedagent.com"
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                
                if data.get("is_oa"):
                    best_location = data.get("best_oa_location", {})
                    if best_location:
                        pdf_url = best_location.get("url_for_pdf")
                        if pdf_url:
                            return pdf_url
                            
        except Exception as e:
            logger.warning(f"Unpaywall error for DOI {doi}: {e}")
            
        return None
