"""
Manages persistent storage of retrieved paper metadata per conversation.
Allows referencing retrieved papers without querying the vector database.
"""

from typing import Dict, List, Any

class ConversationPaperStore:
    
    def __init__(self):
        # Maps conversation_id to list of paper dicts
        self.papers: Dict[str, List[Dict[str, Any]]] = {}
        
    def save_papers(self, conversation_id: str, papers: List[Dict[str, Any]]) -> None:
        """Save retrieved papers for a conversation."""
        if conversation_id not in self.papers:
            self.papers[conversation_id] = []
        self.papers[conversation_id].extend(papers)
        
    def get_papers(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get saved papers for a conversation."""
        return self.papers.get(conversation_id, [])
        
    def clear_papers(self, conversation_id: str) -> None:
        """Clear saved papers for a conversation."""
        if conversation_id in self.papers:
            del self.papers[conversation_id]

# Global instance
_paper_store = None

def get_conversation_paper_store() -> ConversationPaperStore:
    """Get or create the global conversation paper store instance."""
    global _paper_store
    if _paper_store is None:
        _paper_store = ConversationPaperStore()
    return _paper_store
