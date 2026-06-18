"""
Manages chat histories and state per conversation using persistent storage.
"""

from typing import Dict, List, Any
from langchain_core.messages import BaseMessage
from src.storage.conversation_repository import get_conversation_repository

class ConversationManager:
    
    def __init__(self):
        self.repo = get_conversation_repository()
        
    def create_conversation(self, conversation_id: str, user_id: str = None) -> None:
        """Create a new conversation."""
        self.repo.create_conversation(conversation_id, user_id)
            
    def get_conversation(self, conversation_id: str, user_id: str = None) -> Dict[str, Any]:
        """Get an existing conversation."""
        conv = self.repo.get_conversation(conversation_id)
        if not conv:
            self.create_conversation(conversation_id, user_id)
            return self.repo.get_conversation(conversation_id)
        return conv
        
    def append_message(self, conversation_id: str, message: BaseMessage) -> None:
        """Append a message to the conversation."""
        self.repo.append_message(conversation_id, message)
        
    def get_messages(self, conversation_id: str) -> List[BaseMessage]:
        """Get all messages for a conversation."""
        conv = self.get_conversation(conversation_id)
        return conv["messages"]
        
    def set_papers_found(self, conversation_id: str, found: bool) -> None:
        """Update papers_found state."""
        self.repo.update_papers_found(conversation_id, found)
        
    def get_papers_found(self, conversation_id: str) -> bool:
        """Get papers_found state."""
        conv = self.get_conversation(conversation_id)
        return conv["papers_found"]
        
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation."""
        self.repo.delete_conversation(conversation_id)

# Global instance
_conversation_manager = None

def get_conversation_manager() -> ConversationManager:
    """Get or create the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
