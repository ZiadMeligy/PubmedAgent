import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.services.chat_service import ChatService
from src.services.conversation_manager import get_conversation_manager

app = FastAPI(title="Biomedical Literature Retrieval API")

chat_service = ChatService()
conversation_manager = get_conversation_manager()


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    papers_found: bool
    timestamp: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/conversation/new")
def create_conversation():
    new_id = str(uuid.uuid4())
    conversation_manager.create_conversation(new_id)
    return {"conversation_id": new_id, "status": "created"}


@app.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    if conversation_id not in conversation_manager.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Return serializable summary
    conv = conversation_manager.get_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "message_count": len(conv["messages"]),
        "papers_found": conv["papers_found"],
        "timestamp": conv["timestamp"]
    }


@app.delete("/conversation/{conversation_id}")
def delete_conversation(conversation_id: str):
    if conversation_id not in conversation_manager.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation_manager.clear_conversation(conversation_id)
    # Could also clear vector store and paper store for this ID here
    
    return {"status": "deleted"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    conv_id = request.conversation_id
    if not conv_id:
        conv_id = str(uuid.uuid4())
        conversation_manager.create_conversation(conv_id)
    
    # Process through ChatService
    result = chat_service.chat(conv_id, request.message)
    
    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
        papers_found=result["papers_found"],
        timestamp=result["timestamp"]
    )