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
import requests
import math
from datetime import datetime

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
# ABSTRACT CHUNKING
# -------------------------

def chunk_abstract(abstract: str, sentences_per_chunk: int = 2) -> List[str]:
    """
    Split abstract into semantic chunks (2-4 sentences per chunk).
    
    Args:
        abstract: Full abstract text
        sentences_per_chunk: Number of sentences per chunk (default 2)
    
    Returns:
        List of abstract chunks
    """
    if not abstract or abstract == "No abstract available":
        return [abstract]
    
    # Split by periods followed by space (simple sentence splitter)
    # Handle edge cases like "et al.", "Dr.", "etc."
    sentences = re.split(r'(?<=[.!?])\s+', abstract.strip())
    
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        chunk = ' '.join(sentences[i:i+sentences_per_chunk])
        if chunk.strip():
            chunks.append(chunk.strip())
    
    return chunks if chunks else [abstract]


# -------------------------
# SCORING FUNCTIONS
# -------------------------

def compute_recency_score(publication_year: int) -> float:
    """
    Compute recency score normalized to [0, 1].
    
    Newer papers receive higher scores using exponential decay.
    
    Args:
        publication_year: Year of publication (e.g., 2024)
    
    Returns:
        Recency score in range [0, 1]
    """
    if publication_year is None:
        return 0.0
    
    current_year = datetime.now().year
    years_ago = max(0, current_year - publication_year)
    
    # Exponential decay: e^(-decay_rate * years_ago)
    # decay_rate = 0.15 means papers lose ~14% of recency per year
    decay_rate = 0.15
    recency = np.exp(-decay_rate * years_ago)
    
    return float(recency)


def compute_citation_score(citation_count: int) -> float:
    """
    Compute citation score normalized to [0, 1] using log scaling.
    
    Args:
        citation_count: Number of citations
    
    Returns:
        Citation score in range [0, 1]
    """
    if citation_count is None or citation_count <= 0:
        return 0.0
    
    # Log scale: log(1 + citations) normalized
    # Using log1p for better numerical stability
    log_citations = np.log1p(citation_count)
    
    # Normalize by assuming max reasonable citations (e.g., 10000)
    # This puts highly cited papers (>10000 citations) near 1.0
    max_log = np.log1p(10000)
    citation_score = min(1.0, log_citations / max_log)
    
    return float(citation_score)


# -------------------------
# CITATION RETRIEVAL (DOI-based)
# -------------------------

class PubMedCitationFinder:
    """Retrieve citation counts from OpenAlex and Semantic Scholar via DOI."""
    
    PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    OPENALEX_BASE = "https://api.openalex.org"
    SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 5

    def get_paper_info_from_pmid(self, pmid: str) -> dict:
        """Extract DOI from PubMed ID."""
        try:
            url = f"{self.PUBMED_BASE}/esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
            }
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()

            article = response.json()["result"][str(pmid)]

            doi = None
            for item in article.get("articleids", []):
                if item.get("idtype") == "doi":
                    doi = item["value"]
                    break

            if not doi:
                return None

            return {
                "pmid": pmid,
                "title": article.get("title"),
                "doi": doi,
            }
        except Exception:
            return None

    def get_openalex_metrics(self, doi: str) -> dict:
        """Get citation count from OpenAlex via DOI."""
        try:
            doi_clean = doi.lower().replace("https://doi.org/", "")
            url = f"{self.OPENALEX_BASE}/works/https://doi.org/{doi_clean}"
            response = self.session.get(url, timeout=5)

            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "openalex_citations": data.get("cited_by_count"),
            }
        except Exception:
            return None

    def get_semantic_scholar_metrics(self, doi: str) -> dict:
        """Get citation count from Semantic Scholar via DOI."""
        try:
            doi_clean = doi.lower().replace("https://doi.org/", "")
            url = f"{self.SEMANTIC_SCHOLAR_BASE}/paper/DOI:{doi_clean}"
            params = {"fields": "citationCount"}
            response = self.session.get(url, params=params, timeout=5)

            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "semantic_scholar_citations": data.get("citationCount"),
            }
        except Exception:
            return None

    def get_citations_for_pmid(self, pmid: str) -> int:
        """
        Get citation count for a paper using PMID.
        
        Returns the maximum citation count from available sources.
        """
        try:
            paper_info = self.get_paper_info_from_pmid(pmid)
            if not paper_info or not paper_info.get("doi"):
                return 0

            doi = paper_info["doi"]
            
            # Try OpenAlex first (usually more complete)
            openalex = self.get_openalex_metrics(doi) or {}
            openalex_citations = openalex.get("openalex_citations", 0) or 0
            
            # Try Semantic Scholar as backup
            semantic = self.get_semantic_scholar_metrics(doi) or {}
            semantic_citations = semantic.get("semantic_scholar_citations", 0) or 0
            
            # Return the maximum available
            return max(int(openalex_citations), int(semantic_citations))
        except Exception:
            return 0


# Initialize citation finder
_citation_finder = PubMedCitationFinder()


def get_citations_for_pmid(pubmed_id: str) -> int:
    """
    Retrieve citation count for a PubMed ID.
    
    Uses DOI lookup via OpenAlex and Semantic Scholar APIs.
    
    Args:
        pubmed_id: PubMed ID string
    
    Returns:
        Citation count (0 if unavailable)
    """
    if not pubmed_id or pubmed_id == "N/A":
        return 0
    
    return _citation_finder.get_citations_for_pmid(pubmed_id)


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
        
        # Extract publication year
        publication_year = None
        if hasattr(article, 'publication_date') and article.publication_date:
            try:
                # publication_date is typically a datetime object or string
                if isinstance(article.publication_date, str):
                    publication_year = int(article.publication_date.split('-')[0]) if article.publication_date else None
                else:
                    publication_year = article.publication_date.year if hasattr(article.publication_date, 'year') else None
            except (ValueError, AttributeError):
                publication_year = None
        
        papers.append({
            "title": title,
            "abstract": abstract,
            "pubmed_id": pubmed_id,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            "publication_year": publication_year,
            "citation_count": None,  # Will be filled later
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
    Stage 2: Rank papers by abstract similarity using chunk-based retrieval.
    
    Also compute recency scores, citation scores, and composite scores.
    
    Args:
        query: User's search query
        papers: Top 10 papers from title ranking
    
    Returns:
        Top 5 papers ranked by composite score
    """
    query_embedding = get_embeddings([query], use_instruction=True)[0]
    
    # Process each paper
    for paper in papers:
        # --- ABSTRACT CHUNKING AND SIMILARITY ---
        abstract = paper["abstract"]
        chunks = chunk_abstract(abstract)
        
        # Embed all chunks
        chunk_embeddings = get_embeddings(chunks, use_instruction=False)
        
        # Compute similarities for each chunk
        chunk_similarities = compute_similarity(query_embedding, chunk_embeddings)
        
        # Use maximum chunk similarity as the paper's abstract score
        abstract_similarity = float(np.max(chunk_similarities)) if len(chunk_similarities) > 0 else 0.0
        paper["abstract_similarity"] = abstract_similarity
        
        # --- RECENCY SCORE ---
        recency_score = compute_recency_score(paper["publication_year"])
        paper["recency_score"] = recency_score
        
        # --- CITATION COUNT AND CITATION SCORE ---
        citation_count = get_citations_for_pmid(paper["pubmed_id"])
        paper["citation_count"] = citation_count
        citation_score = compute_citation_score(citation_count)
        paper["citation_score"] = citation_score
        
        # --- COMPOSITE SCORE ---
        # Average of semantic similarity, recency, and citation scores
        composite_score = (abstract_similarity + recency_score + citation_score) / 3
        paper["composite_score"] = composite_score
    
    # Sort by composite score and keep top 5
    ranked_papers = sorted(papers, key=lambda x: x["composite_score"], reverse=True)[:5]
    
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
    Format ranked papers for display with all metrics.
    
    Args:
        query: Original search query
        papers: List of ranked papers with all scores
    
    Returns:
        Formatted string output
    """
    if not papers:
        return f"Query: {query}\n\nNo papers found."
    
    output = f"Query: {query}\n\n"
    output += "Top 5 Ranked Papers (By Composite Score)\n"
    output += "=" * 90 + "\n\n"
    
    for rank, paper in enumerate(papers, 1):
        output += f"Rank: {rank}\n"
        output += f"Title: {paper['title']}\n"
        output += f"Publication Year: {paper['publication_year'] if paper['publication_year'] else 'Unknown'}\n"
        output += f"PubMed ID: {paper['pubmed_id']}\n"
        output += f"URL: {paper['url']}\n"
        output += "\n"
        output += f"  Abstract Similarity:  {paper['abstract_similarity']:.4f}\n"
        output += f"  Recency Score:       {paper['recency_score']:.4f}\n"
        output += f"  Citation Count:      {paper['citation_count']}\n"
        output += f"  Citation Score:      {paper['citation_score']:.4f}\n"
        output += f"  Composite Score:     {paper['composite_score']:.4f}\n"
        output += "-" * 90 + "\n\n"
    
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