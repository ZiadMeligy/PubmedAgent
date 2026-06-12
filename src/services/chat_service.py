# src/services/chat_service.py

from langchain_core.messages import HumanMessage
from src.graph.builder import compiled_graph
from src.services.conversation_manager import get_conversation_manager

class ChatService:

    def __init__(self):
        self.conversation_manager = get_conversation_manager()

    def chat(self, conversation_id: str, user_message: str) -> dict:
        """
        Process a user message for a specific conversation.
        """
        # Load conversation state
        conv = self.conversation_manager.get_conversation(conversation_id)
        
        # Build state
        state = {
            "messages": conv["messages"] + [HumanMessage(content=user_message)],
            "papers_found": conv["papers_found"],
            "conversation_id": conversation_id
        }

        # Invoke LangGraph
        result = compiled_graph.invoke(state)

        # Update manager state
        self.conversation_manager.conversations[conversation_id]["messages"] = result["messages"]
        self.conversation_manager.conversations[conversation_id]["papers_found"] = result["papers_found"]
        
        # Get latest message content
        response_content = result["messages"][-1].content if result["messages"] else ""

        return {
            "conversation_id": conversation_id,
            "response": response_content,
            "papers_found": result["papers_found"],
            "timestamp": self.conversation_manager.conversations[conversation_id]["timestamp"]
        }