from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class FullTextProvider(ABC):
    """
    Abstract base class for all Full-Text PDF providers.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass
        
    @abstractmethod
    async def check_availability(self, paper: Dict[str, Any]) -> Optional[str]:
        """
        Check if a free open-access PDF is available for the given paper.
        
        Args:
            paper: A dictionary containing paper metadata ('pubmed_id', 'doi', 'title', etc.)
            
        Returns:
            The direct PDF URL if available, else None.
        """
        pass
