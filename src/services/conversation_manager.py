"""
Manages chat histories and state per conversation in-memory.
Designed to be easily replaced by Redis or a database in the future.
"""

from typing import Dict, List, Any
import datetime
from langchain_core.messages import BaseMessage

class ConversationManager:
    
    def __init__(self):
        # Maps conversation_id to conversation state
        self.conversations: Dict[str, Dict[str, Any]] = {}
        
    def create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {
                "messages": [],
                "papers_found": False,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get an existing conversation."""
        if conversation_id not in self.conversations:
            self.create_conversation(conversation_id)
        return self.conversations[conversation_id]
        
    def append_message(self, conversation_id: str, message: BaseMessage) -> None:
        """Append a message to the conversation."""
        conv = self.get_conversation(conversation_id)
        conv["messages"].append(message)
        conv["timestamp"] = datetime.datetime.now().isoformat()
        
    def get_messages(self, conversation_id: str) -> List[BaseMessage]:
        """Get all messages for a conversation."""
        return self.get_conversation(conversation_id)["messages"]
        
    def set_papers_found(self, conversation_id: str, found: bool) -> None:
        """Update papers_found state."""
        conv = self.get_conversation(conversation_id)
        conv["papers_found"] = found
        
    def get_papers_found(self, conversation_id: str) -> bool:
        """Get papers_found state."""
        return self.get_conversation(conversation_id)["papers_found"]
        
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

# Global instance
_conversation_manager = None

def get_conversation_manager() -> ConversationManager:
    """Get or create the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
