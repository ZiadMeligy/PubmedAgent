"""Persistent ranked-paper metadata for post-search QA."""

from typing import List, Dict, Any
from src.storage.conversation_repository import get_conversation_repository

class ConversationPaperStore:
    
    def __init__(self):
        self.repo = get_conversation_repository()
        
    def save_papers(self, conversation_id: str, papers: List[Dict[str, Any]]) -> None:
        """Replace the active ranked set for a conversation."""
        self.repo.save_ranked_papers(conversation_id, papers)
        
    def get_papers(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get the active ranked set, including stable 1-based ranks."""
        return self.repo.get_ranked_papers(conversation_id)
        
    def clear_papers(self, conversation_id: str) -> None:
        self.repo.clear_ranked_papers(conversation_id)

# Global instance
_paper_store = None

def get_conversation_paper_store() -> ConversationPaperStore:
    """Get or create the global conversation paper store instance."""
    global _paper_store
    if _paper_store is None:
        _paper_store = ConversationPaperStore()
    return _paper_store
