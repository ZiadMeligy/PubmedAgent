"""
Graph nodes for the LangGraph workflow with paper search and Q&A modes.
"""

import os
import json
import re
import logging
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from operator import add as add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from src.llm.model import get_system_prompt, invoke_llm
from src.llm.qa_model import get_qa_system_prompt, invoke_qa_model
from src.llm.reranker import rerank_chunks, format_chunks_for_qa
from src.retrieval.search import hierarchical_retrieve
from src.formatting import format_ranked_papers
from src.storage.paper_manager import get_paper_store
from src.services.paper_store import get_conversation_paper_store
from src.nlp.scispacy_extractor import extract_entities
from src.nlp.entity_ranking import rank_entity_importance

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the agent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    papers_found: bool
    conversation_id: str
    response_type: str
    latest_papers: list
    latest_references: list
    alpha: float
    beta: float
    gamma: float


def model_call(state: AgentState):
    """Call the LLM to generate queries from clinical notes or analyze retrieved papers"""
    system_prompt = get_system_prompt()
    messages = list(state["messages"])
    
    # Extract entities from the last human message to aid query generation
    last_msg = messages[-1]
    if isinstance(last_msg, HumanMessage):
        raw_entities = extract_entities(last_msg.content).get("Biomedical Entities", [])
        ranked_entities = rank_entity_importance(raw_entities)
        entities_str = json.dumps(ranked_entities, indent=2)
        # Inject entities as context
        context_msg = HumanMessage(content=f"[SYSTEM CONTEXT - EXTRACTED & RANKED ENTITIES]\n{entities_str}\n[END CONTEXT]\n\nUser Message:\n{last_msg.content}")
        messages[-1] = context_msg
    
    full_messages = [system_prompt] + messages
    response = invoke_llm(full_messages)
    
    return {"messages": [response], "response_type": "chat"}


def execute_tools_if_needed(state: AgentState) -> dict:
    """Check if the last message contains a tool call and execute it"""
    messages = list(state["messages"])
    last_message = messages[-1]
    conversation_id = state.get("conversation_id", "default")
    
    # Check if the message contains a tool call
    if hasattr(last_message, 'content') and '<TOOL_CALL>' in last_message.content:
        # Extract the tool call JSON
        match = re.search(r'<TOOL_CALL>(.*?)</TOOL_CALL>', last_message.content, re.DOTALL)
        if match:
            try:
                tool_data = json.loads(match.group(1))
                tool_name = tool_data.get("tool")
                
                if tool_name == "search_pubmed":
                    queries_dict = tool_data.get("queries", {})
                    
                    # Extract the original user prompt
                    original_prompt = ""
                    for msg in reversed(messages):
                        if isinstance(msg, HumanMessage):
                            content = msg.content
                            if "[SYSTEM CONTEXT" in content and "User Message:\\n" in content:
                                content = content.split("User Message:\\n")[-1]
                            original_prompt = content
                            break
                    
                    # Execute hierarchical retrieval with multi-query and original prompt
                    alpha = state.get("alpha", 0.8)
                    beta = state.get("beta", 0.1)
                    gamma = state.get("gamma", 0.1)
                    ranked_papers = hierarchical_retrieve(
                        original_prompt=original_prompt, 
                        queries=queries_dict, 
                        alpha=alpha, beta=beta, gamma=gamma
                    )
                    
                    # Store papers in the conversational paper store
                    if ranked_papers:
                        paper_store_manager = get_conversation_paper_store()
                        paper_store_manager.save_papers(conversation_id, ranked_papers)
                        
                        # Add papers to Qdrant vector store
                        vector_store = get_paper_store()
                        chunks_added = vector_store.add_papers_to_store(ranked_papers, conversation_id=conversation_id)
                        logger.info(f"Added {chunks_added} abstract chunks to vector store for conversation {conversation_id}")
                    
                    # Format the refined results with all metrics
                    # Pass a representative query string to formatter
                    repr_query = " | ".join(queries_dict.values()) if isinstance(queries_dict, dict) else str(queries_dict)
                    formatted_results = format_ranked_papers(repr_query, ranked_papers)
                    
                    # Return the formatted results directly as an AI message
                    result_message = AIMessage(content=f"=== PUBMED SEARCH COMPLETE ===\n\n{formatted_results}")
                    
                    # Add the tool result as a message and mark papers as found
                    return {
                        "messages": [result_message],
                        "papers_found": bool(ranked_papers),
                        "response_type": "paper_search",
                        "latest_papers": ranked_papers
                    }
            except json.JSONDecodeError:
                logger.error("Failed to parse tool call JSON")
    
    # No tool call found or invalid format
    return {"messages": []}


def qa_call(state: AgentState):
    """Call the Q&A model to answer questions about papers"""
    messages = list(state["messages"])
    conversation_id = state.get("conversation_id", "default")
    
    # The last message is the model's <QA_CALL>
    # The user's question should be the message before that
    question = ""
    if len(messages) >= 2:
        question = messages[-2].content if hasattr(messages[-2], 'content') else ""
    
    # Retrieve relevant chunks from vector store for this conversation
    paper_store = get_paper_store()
    retrieved_chunks = paper_store.search_for_answer(question, conversation_id=conversation_id, top_k=5)
    
    # Rerank the chunks
    reranked_chunks = rerank_chunks(question, retrieved_chunks, top_k=3)
    
    # Format chunks for Q&A model
    context = format_chunks_for_qa(reranked_chunks)
    
    if os.environ.get("DEBUG_QA_CONTEXT", "").lower() == "true":
        logger.debug("QA CONTEXT being sent to model:")
        for c in reranked_chunks:
            logger.debug(f"  Title: {c.get('title')}")
            logger.debug(f"  Score: {c.get('rerank_score')}")
            logger.debug(f"  Chunk: {c.get('text', '')[:100]}...")
        
    # Prepare messages for Q&A model with context
    qa_system_prompt = get_qa_system_prompt()
    qa_messages = [
        qa_system_prompt,
        HumanMessage(content=f"CONTEXT:\n{context}\n\nQUESTION: {question}")
    ]
    
    # Invoke Q&A model
    response = invoke_qa_model(qa_messages)
    
    # Extract references with deduplication
    seen_pmids = set()
    references = []
    for c in reranked_chunks:
        pmid = c.get('pmid')
        if pmid and pmid not in seen_pmids:
            seen_pmids.add(pmid)
            references.append({
                "title": c.get('title', 'Unknown'),
                "pmid": pmid,
                "url": c.get('url') or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "year": c.get('year')
            })
    
    return {
        "messages": [response],
        "response_type": "qa",
        "latest_references": references
    }
