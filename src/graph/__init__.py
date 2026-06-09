"""
Graph nodes for the LangGraph workflow with paper search and Q&A modes.
"""

import json
import re
from typing import TypedDict, Annotated, Sequence
from operator import add as add_messages
from langchain_core.messages import BaseMessage, HumanMessage
from src.llm.model import get_system_prompt, invoke_llm
from src.llm.qa_model import get_qa_system_prompt, invoke_qa_model
from src.llm.reranker import rerank_chunks, format_chunks_for_qa
from src.retrieval.search import hierarchical_retrieve
from src.formatting import format_ranked_papers
from src.storage.paper_manager import get_paper_store


class AgentState(TypedDict):
    """State for the agent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    papers_found: bool  # Track if papers have been found (for mode routing)
    mode: str  # 'search' or 'qa'


def model_call(state: AgentState):
    """Call the LLM to generate queries from clinical notes or analyze retrieved papers"""
    system_prompt = get_system_prompt()
    
    messages = [system_prompt] + list(state["messages"])
    response = invoke_llm(messages)
    
    return {"messages": [response]}


def execute_tools_if_needed(state: AgentState) -> dict:
    """Check if the last message contains a tool call and execute it"""
    messages = list(state["messages"])
    last_message = messages[-1]
    
    # Check if the message contains a tool call
    if hasattr(last_message, 'content') and '<TOOL_CALL>' in last_message.content:
        # Extract the tool call JSON
        match = re.search(r'<TOOL_CALL>(.*?)</TOOL_CALL>', last_message.content, re.DOTALL)
        if match:
            try:
                tool_data = json.loads(match.group(1))
                tool_name = tool_data.get("tool")
                
                if tool_name == "search_pubmed":
                    query = tool_data.get("query")
                    
                    # Execute hierarchical retrieval directly in tool node
                    # This combines: search_pubmed -> rank_titles -> rank_abstracts
                    ranked_papers = hierarchical_retrieve(query)
                    
                    # Format the refined results with all metrics
                    formatted_results = format_ranked_papers(query, ranked_papers)
                    
                    # Add papers to Qdrant vector store
                    if ranked_papers:
                        paper_store = get_paper_store()
                        chunks_added = paper_store.add_papers_to_store(ranked_papers)
                        print(f"✓ Added {chunks_added} abstract chunks to vector store")
                    
                    # Return the refined top 5 papers with scores to the LLM
                    result_message = f"""
                        === PUBMED SEARCH COMPLETE ===

                        {formatted_results}

                        """
                    
                    # Add the tool result as a message and mark papers as found
                    return {
                        "messages": [HumanMessage(content=result_message)],
                        "papers_found": bool(ranked_papers),
                        "mode": "qa"  # Switch to Q&A mode after papers found
                    }
            except json.JSONDecodeError:
                pass
    
    # No tool call found or invalid format
    return {"messages": []}


def qa_call(state: AgentState):
    """Call the Q&A model to answer questions about papers"""
    messages = list(state["messages"])
    last_message = messages[-1]
    
    # Extract the question
    question = last_message.content if hasattr(last_message, 'content') else ""
    
    # Retrieve relevant chunks from vector store
    paper_store = get_paper_store()
    retrieved_chunks = paper_store.search_for_answer(question, top_k=5)
    
    # Rerank the chunks
    reranked_chunks = rerank_chunks(question, retrieved_chunks, top_k=3)
    
    # Format chunks for Q&A model
    context = format_chunks_for_qa(reranked_chunks)
    
    # Prepare messages for Q&A model with context
    qa_system_prompt = get_qa_system_prompt()
    qa_messages = [
        qa_system_prompt,
        HumanMessage(content=f"CONTEXT:\n{context}\n\nQUESTION: {question}")
    ]
    
    # Invoke Q&A model
    response = invoke_qa_model(qa_messages)
    
    return {"messages": [response]}
