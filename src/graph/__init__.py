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
from src.qa.multimodal import build_qa_message
from src.qa.paper_selection import resolve_paper_selection

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the agent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    papers_found: bool
    conversation_id: str
    response_type: str
    latest_papers: list
    latest_references: list
    latest_artifacts: list
    alpha: float
    beta: float
    gamma: float
    journal_quality_enabled: bool
    minimum_sjr: float
    retrieval_config: dict


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
                    journal_quality_enabled = state.get("journal_quality_enabled", False)
                    minimum_sjr = state.get("minimum_sjr", 10.0)
                    
                    retrieval_config = {
                        "similarity": alpha,
                        "recency": beta,
                        "citation": gamma,
                        "journal_quality_enabled": journal_quality_enabled,
                        "minimum_sjr": minimum_sjr
                    }
                    
                    ranked_papers = hierarchical_retrieve(
                        original_prompt=original_prompt, 
                        queries=queries_dict, 
                        alpha=alpha,
                        beta=beta,
                        gamma=gamma,
                        journal_quality_enabled=journal_quality_enabled,
                        minimum_sjr=minimum_sjr
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
                    result_message = AIMessage(
                        content=f"=== PUBMED SEARCH COMPLETE ===\n\n{formatted_results}",
                        additional_kwargs={"retrieval_config": retrieval_config}
                    )
                    
                    # Add the tool result as a message and mark papers as found
                    return {
                        "messages": [result_message],
                        "papers_found": bool(ranked_papers),
                        "response_type": "paper_search",
                        "latest_papers": ranked_papers,
                        "retrieval_config": retrieval_config
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
        
    latest_papers = state.get("latest_papers", [])
    selection = resolve_paper_selection(question, latest_papers)

    if selection.explicit and selection.missing_ranks:
        available = ", ".join(str(p.get("rank")) for p in latest_papers) or "none"
        missing = ", ".join(str(rank) for rank in selection.missing_ranks)
        response = AIMessage(
            content=(
                f"Ranked paper {missing} is not available in the latest search result. "
                f"Available ranks: {available}."
            )
        )
        return {
            "messages": [response],
            "response_type": "qa",
            "latest_references": [],
            "latest_artifacts": [],
        }

    if not selection.papers:
        response = AIMessage(
            content=(
                "There is no active ranked-paper set for this conversation. "
                "Please run a PubMed search first."
            )
        )
        return {
            "messages": [response],
            "response_type": "qa",
            "latest_references": [],
            "latest_artifacts": [],
        }
    
    # Query rewriting is constrained to the deterministically selected papers.
    search_query = question
    if question:
        paper_list_str = "\n".join(
            f"Rank {paper.get('rank')}: {paper.get('title', 'Unknown Title')} "
            f"(PMID {paper.get('pubmed_id') or paper.get('pmid')})"
            for paper in selection.papers
        )
        
        rewrite_prompt = f"""You are an expert search query rewriter. 
The user is asking a question in a conversational context about some retrieved medical papers.
The following paper selection is fixed and must not be changed:
{paper_list_str}

User's raw question: {question}

Rewrite this into one concise standalone evidence-retrieval query.
Preserve comparison intent, outcomes, methods, populations, tables, and figures.
Replace ordinal references with the exact selected paper titles.
Do NOT answer the question. Just output the rewritten query string and nothing else."""
        
        try:
            from langchain_core.messages import SystemMessage
            rewrite_response = invoke_llm([SystemMessage(content=rewrite_prompt)])
            if hasattr(rewrite_response, 'content'):
                search_query = rewrite_response.content.strip()
            else:
                search_query = str(rewrite_response).strip()
            logger.info(f"Rewrote QA query: '{question}' -> '{search_query}'")
        except Exception as e:
            logger.error(f"Failed to rewrite query: {e}")
            search_query = question

    # Exact PMID filtering happens inside Qdrant before semantic scoring.
    paper_store = get_paper_store()
    retrieved_chunks = paper_store.search_for_answer(
        search_query,
        conversation_id=conversation_id,
        top_k=8,
        pmids=selection.pmids,
        lexical_query=question,
    )

    rank_by_pmid = {
        str(p.get("pubmed_id") or p.get("pmid")): p.get("rank")
        for p in selection.papers
    }
    for chunk in retrieved_chunks:
        chunk["rank"] = rank_by_pmid.get(str(chunk.get("pmid")))

    comparison_requested = (
        len(selection.papers) > 1
        and any(
            term in question.lower()
            for term in ("compare", "comparison", "versus", " vs ", "difference", "similar")
        )
    )
    balance_pmids = selection.pmids if selection.explicit or comparison_requested else None
    per_paper_k = 6 if len(selection.papers) <= 2 else 4
    reranked_chunks = rerank_chunks(
        search_query,
        retrieved_chunks,
        top_k=per_paper_k if balance_pmids else 10,
        selected_pmids=balance_pmids,
    )
    
    # Format chunks for Q&A model
    context = format_chunks_for_qa(reranked_chunks)
    
    if os.environ.get("DEBUG_QA_CONTEXT", "").lower() == "true":
        logger.debug("QA CONTEXT being sent to model:")
        for c in reranked_chunks:
            logger.debug(f"  Title: {c.get('title')}")
            logger.debug(f"  Score: {c.get('rerank_score')}")
            logger.debug(f"  Chunk: {c.get('text', '')[:100]}...")
        
    # Prepare messages for Q&A model with context (use rewritten query)
    qa_system_prompt = get_qa_system_prompt()
    qa_messages = [
        qa_system_prompt,
        build_qa_message(context, question, reranked_chunks),
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
                "year": c.get('year'),
                "rank": c.get("rank"),
            })

    artifacts = []
    seen_artifacts = set()
    for chunk in reranked_chunks:
        artifact_id = chunk.get("artifact_id")
        if not artifact_id or artifact_id in seen_artifacts:
            continue
        seen_artifacts.add(artifact_id)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "type": chunk.get("content_type"),
                "pmid": str(chunk.get("pmid") or ""),
                "rank": chunk.get("rank"),
                "title": chunk.get("title") or "",
                "label": chunk.get("label") or chunk.get("section") or "Paper artifact",
                "page_number": chunk.get("page_number"),
                "url": chunk.get("artifact_url"),
            }
        )
    
    return {
        "messages": [response],
        "response_type": "qa",
        "latest_references": references,
        "latest_artifacts": artifacts,
    }
