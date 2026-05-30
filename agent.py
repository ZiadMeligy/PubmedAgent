import os
import json
import re
from typing import TypedDict, Annotated, Sequence, List, Dict
from operator import add as add_messages
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq

from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage
)

load_dotenv()

from pymed import PubMed

# -------------------------
# STATE
# -------------------------

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# -------------------------
# BGE MODEL SETUP
# -------------------------
embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')

# -------------------------
# EMBEDDING FUNCTIONS
# -------------------------

def get_embeddings(texts: List[str], use_instruction: bool = False) -> np.ndarray:
    """
    Generate embeddings using BGE-small-en-v1.5.
    
    Args:
        texts: List of text strings to embed
        use_instruction: If True, prepend BGE retrieval instruction (for queries)
    
    Returns:
        Normalized embeddings as numpy array
    """
    if use_instruction:
        instruction = "Represent this sentence for searching relevant passages: "
        texts_to_embed = [instruction + text for text in texts]
    else:
        texts_to_embed = texts
    
    embeddings = embedding_model.encode(texts_to_embed, normalize_embeddings=True)
    return embeddings


def compute_similarity(query_embedding: np.ndarray, document_embeddings: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between query and documents.
    
    Args:
        query_embedding: Single query embedding (1D array)
        document_embeddings: Multiple document embeddings (2D array)
    
    Returns:
        Similarity scores as 1D array
    """
    similarities = cosine_similarity([query_embedding], document_embeddings)[0]
    return similarities


# -------------------------
# RETRIEVAL FUNCTIONS
# -------------------------

def search_pubmed(query: str) -> List[Dict]:
    """
    Search PubMed for medical research papers.
    
    Args:
        query: Search query string
    
    Returns:
        List of paper dictionaries with metadata
    """
    pubmed = PubMed(tool="pubmed", email="your_email@example.com")
    results = list(pubmed.query(query, max_results=20))

    papers = []

    for article in results:
        title = article.title or "No title"
        abstract = article.abstract or "No abstract available"
        
        # Extract only the first PubMed ID (some fields contain multiple IDs)
        pubmed_id_raw = article.pubmed_id or "N/A"
        pubmed_id = pubmed_id_raw.split()[0] if pubmed_id_raw != "N/A" else "N/A"
        
        papers.append({
            "title": title,
            "abstract": abstract,
            "pubmed_id": pubmed_id,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
        })

    return papers


def rank_titles(query: str, papers: List[Dict]) -> List[Dict]:
    """
    Stage 1: Rank papers by title similarity.
    
    Args:
        query: User's search query
        papers: List of paper dictionaries from search_pubmed
    
    Returns:
        Top 10 papers ranked by title similarity with scores
    """
    titles = [paper["title"] for paper in papers]
    
    # Get embeddings
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    title_embeddings = get_embeddings(titles, use_instruction=False)
    
    # Compute similarities
    title_similarities = compute_similarity(query_embedding, title_embeddings)
    
    # Add similarity scores and sort
    for i, paper in enumerate(papers):
        paper["title_similarity"] = float(title_similarities[i])
    
    # Sort by title similarity and keep top 10
    ranked_papers = sorted(papers, key=lambda x: x["title_similarity"], reverse=True)[:10]
    
    return ranked_papers


def rank_abstracts(query: str, papers: List[Dict]) -> List[Dict]:
    """
    Stage 2: Rank papers by abstract similarity.
    
    Args:
        query: User's search query
        papers: Top 10 papers from title ranking
    
    Returns:
        Top 5 papers ranked by abstract similarity
    """
    abstracts = [paper["abstract"] for paper in papers]
    
    # Get embeddings
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    abstract_embeddings = get_embeddings(abstracts, use_instruction=False)
    
    # Compute similarities
    abstract_similarities = compute_similarity(query_embedding, abstract_embeddings)
    
    # Add similarity scores
    for i, paper in enumerate(papers):
        paper["abstract_similarity"] = float(abstract_similarities[i])
        # Compute final similarity as average of title and abstract similarity
        paper["final_similarity"] = (paper["title_similarity"] + paper["abstract_similarity"]) / 2
    
    # Sort by final similarity and keep top 5
    ranked_papers = sorted(papers, key=lambda x: x["final_similarity"], reverse=True)[:5]
    
    return ranked_papers


def hierarchical_retrieve(query: str) -> List[Dict]:
    """
    Execute hierarchical retrieval: title filtering -> abstract ranking.
    
    Args:
        query: User's search query
    
    Returns:
        Top 5 papers with title and abstract similarity scores
    """
    # Stage 1: Retrieve up to 20 papers and rank by titles (keep top 10)
    papers = search_pubmed(query)
    if not papers:
        return []
    
    papers = rank_titles(query, papers)
    
    # Stage 2: Rank top 10 by abstracts (keep top 5)
    papers = rank_abstracts(query, papers)
    
    return papers

# -------------------------
# LLM SETUP
# -------------------------

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0
)


# -------------------------
# MODEL NODE (WITHOUT TOOLS) - UNCHANGED FOR NOW
# -------------------------

def model_call(state: AgentState):
    """Call the LLM without function calling - instead use prompt-based tool invocation"""
    system_prompt = SystemMessage(
        content="""You are a medical literature assistant with expertise in PubMed searches.

When asked about medical research topics, you should:
1. Identify what medical information is needed
2. Call the search_pubmed tool by responding with a JSON block like this:
   <TOOL_CALL>
   {"tool": "search_pubmed", "query": "your search query here"}
   </TOOL_CALL>
3. Wait for the results
4. Analyze and summarize the findings

If you are shown search results, analyze them and provide a comprehensive answer.

Be concise and focused on answering the user's question with the most relevant information."""
    )

    messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(messages)
    
    return {"messages": [response]}


# -------------------------
# TOOL EXECUTION NODE - UNCHANGED FOR NOW
# -------------------------

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
                    result = search_pubmed(query)
                    # Add the tool result as a message
                    return {"messages": [HumanMessage(content=f"Search results for '{query}':\n\n{result}\n\nPlease analyze these results and provide a comprehensive answer to the user's original question.")]}
            except json.JSONDecodeError:
                pass
    
    # No tool call found or invalid format
    return {"messages": []}


# -------------------------
# ROUTER - UNCHANGED FOR NOW
# -------------------------

def should_continue(state: AgentState) -> str:
    """Decide if we should continue with tool execution or end"""
    messages = list(state["messages"])
    last_message = messages[-1]
    
    # If the last message contains a tool call, continue to execute it
    if hasattr(last_message, 'content') and '<TOOL_CALL>' in last_message.content:
        return "tools"
    # Otherwise, we're done
    return "end"


# -------------------------
# GRAPH - UNCHANGED FOR NOW
# -------------------------

graph = StateGraph(AgentState)

graph.add_node("model", model_call)
graph.add_node("tools", execute_tools_if_needed)

graph.set_entry_point("model")

graph.add_conditional_edges(
    "model",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

graph.add_edge("tools", "model")

compiled_graph = graph.compile()


# -------------------------
# FORMATTING UTILITIES
# -------------------------

def format_ranked_papers(query: str, papers: List[Dict]) -> str:
    """
    Format ranked papers for display.
    
    Args:
        query: Original search query
        papers: List of ranked papers with similarity scores
    
    Returns:
        Formatted string output
    """
    if not papers:
        return f"Query: {query}\n\nNo papers found."
    
    output = f"Query: {query}\n\n"
    output += "Top 5 Ranked Papers\n"
    output += "=" * 70 + "\n\n"
    
    for rank, paper in enumerate(papers, 1):
        output += f"Rank: {rank}\n"
        output += f"Title Similarity: {paper['title_similarity']:.4f}\n"
        output += f"Abstract Similarity: {paper['abstract_similarity']:.4f}\n"
        output += f"Final Similarity: {paper['final_similarity']:.4f}\n"
        output += f"Title: {paper['title']}\n"
        output += f"PubMed ID: {paper['pubmed_id']}\n"
        output += f"URL: {paper['url']}\n"
        output += "-" * 70 + "\n\n"
    
    return output


# -------------------------
# MAIN
# -------------------------

if __name__ == "__main__":
    # Test the hierarchical retrieval pipeline directly
    query = "What are the latest treatments for stage III NSCLC using immunotherapy?"
    
    print("Starting hierarchical retrieval...\n")
    
    ranked_papers = hierarchical_retrieve(query)
    
    # Format and print results
    output = format_ranked_papers(query, ranked_papers)
    print(output)