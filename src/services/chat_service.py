"""
Chat service layer — all LangGraph orchestration lives here.
FastAPI routes call this service exclusively.
"""

import logging
from langchain_core.messages import HumanMessage, AIMessage
from src.graph.builder import compiled_graph
from src.services.conversation_manager import get_conversation_manager
from src.api.schemas import (
    PaperSearchResponse, PaperResult,
    QAResponse, ReferenceResult,
    ChatResponse, ErrorResponse,
)

logger = logging.getLogger(__name__)


class ChatService:

    def __init__(self):
        self.conversation_manager = get_conversation_manager()

    def chat(self, conversation_id: str, user_message: str, user_id: str = None):
        """
        Process a user message for a specific conversation.
        Returns a typed Pydantic response model.
        """
        try:
            # 1. Ensure conversation exists
            self.conversation_manager.get_conversation(conversation_id)

            # 2. Save user message
            human_msg = HumanMessage(content=user_message)
            self.conversation_manager.append_message(conversation_id, human_msg)

            # 3. Get full history
            messages = self.conversation_manager.get_messages(conversation_id)
            papers_found = self.conversation_manager.get_papers_found(conversation_id)
            
            # 3.5 Generate and save conversation title if this is the first message
            if len(messages) == 1 and user_message:
                title = user_message[:40] + ("..." if len(user_message) > 40 else "")
                self.conversation_manager.repo.update_conversation_title(conversation_id, title)
                
            # Get user preferences
            repo = self.conversation_manager.repo
            prefs = repo.get_preferences(user_id) if user_id else {"alpha": 0.8, "beta": 0.1, "gamma": 0.1}

            # 4. Build state
            state = {
                "messages": messages,
                "papers_found": papers_found,
                "conversation_id": conversation_id,
                "response_type": "chat",
                "latest_papers": [],
                "latest_references": [],
                "alpha": prefs["alpha"],
                "beta": prefs["beta"],
                "gamma": prefs["gamma"],
            }

            # 5. Invoke LangGraph
            result = compiled_graph.invoke(state)

            # 6. Persist new messages produced by the graph
            new_messages = result["messages"][len(messages):]
            for msg in new_messages:
                self.conversation_manager.append_message(conversation_id, msg)

            self.conversation_manager.set_papers_found(
                conversation_id, result["papers_found"]
            )

            # 7. Build typed response
            response_type = result.get("response_type", "chat")
            latest_content = (
                result["messages"][-1].content if result["messages"] else ""
            )

            if response_type == "paper_search":
                return self._build_paper_search_response(
                    conversation_id, result, latest_content
                )
            elif response_type == "qa":
                return self._build_qa_response(
                    conversation_id, result, latest_content
                )
            else:
                return ChatResponse(
                    conversation_id=conversation_id,
                    response=latest_content,
                )

        except Exception as e:
            logger.exception(f"Error processing chat for {conversation_id}")
            return ErrorResponse(
                conversation_id=conversation_id,
                message=str(e),
            )

    # ── Private helpers ──────────────────────────────────────────

    def _build_paper_search_response(
        self, conversation_id: str, result: dict, text_response: str
    ) -> PaperSearchResponse:
        papers = []
        for i, p in enumerate(result.get("latest_papers", []), 1):
            papers.append(
                PaperResult(
                    rank=i,
                    title=p.get("title", ""),
                    url=p.get("url", ""),
                    journal=p.get("journal"),
                    publication_year=p.get("publication_year"),
                    citation_count=p.get("citation_count"),
                    similarity_score=p.get("abstract_similarity"),
                    composite_score=p.get("composite_score"),
                )
            )
        return PaperSearchResponse(
            conversation_id=conversation_id,
            response=text_response,
            papers_found=result["papers_found"],
            papers=papers,
            retrieval_config=result.get("retrieval_config"),
        )

    def _build_qa_response(
        self, conversation_id: str, result: dict, text_response: str
    ) -> QAResponse:
        refs = []
        for r in result.get("latest_references", []):
            refs.append(
                ReferenceResult(
                    title=r.get("title", ""),
                    pmid=r.get("pmid", ""),
                    url=r.get("url", ""),
                    year=r.get("year"),
                )
            )
        return QAResponse(
            conversation_id=conversation_id,
            response=text_response,
            references=refs,
        )