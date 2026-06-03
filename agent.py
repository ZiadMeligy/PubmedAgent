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


def compute_composite_score(
    similarity_score: float,
    recency_score: float,
    citation_score: float,
    alpha: float,
    beta: float,
    gamma: float,
) -> float:
    """
    Compute weighted composite score with user-controlled parameters.
    
    Weights are automatically normalized to sum to 1.
    
    Args:
        similarity_score: Abstract semantic similarity [0, 1]
        recency_score: Publication recency [0, 1]
        citation_score: Citation impact [0, 1]
        alpha: Weight for similarity
        beta: Weight for recency
        gamma: Weight for citations
    
    Returns:
        Composite score in range [0, 1]
    """
    # Normalize weights
    total = alpha + beta + gamma
    if total == 0:
        # Handle edge case where all weights are 0
        total = 1.0
    
    alpha_norm = alpha / total
    beta_norm = beta / total
    gamma_norm = gamma / total
    
    # Compute weighted score
    composite = (
        alpha_norm * similarity_score +
        gamma_norm * citation_score
    )
    
    return float(composite)


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
    results = list(pubmed.query(query, max_results=100))
    print(f"Retrieved {len(results)} papers from PubMed for query: '{query}'")
    papers = []

    for article in results:
        print(article.publication_date, article.title)
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
    ranked_papers = sorted(papers, key=lambda x: x["title_similarity"], reverse=True)[:40]
    
    return ranked_papers


def rank_abstracts(
    query: str,
    papers: List[Dict],
    alpha: float,
    beta: float,
    gamma: float,
) -> List[Dict]:
    """
    Stage 2: Rank papers by abstract similarity using chunk-based retrieval.
    
    Also compute recency scores, citation scores, and weighted composite scores.
    
    Args:
        query: User's search query
        papers: Top 10 papers from title ranking
        alpha: Weight for semantic similarity (default 0.8)
        beta: Weight for recency (default 0.1)
        gamma: Weight for citations (default 0.1)
    
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
        
        # --- WEIGHTED COMPOSITE SCORE ---
        composite_score = compute_composite_score(
            similarity_score=abstract_similarity,
            recency_score=recency_score,
            citation_score=citation_score,
            alpha=alpha,
            beta=beta,
            gamma=gamma
        )
        paper["composite_score"] = composite_score
        
        # Store weights for output
        paper["alpha"] = alpha
        paper["beta"] = beta
        paper["gamma"] = gamma
    
    # Sort by composite score and keep top 5
    ranked_papers = sorted(papers, key=lambda x: x["composite_score"], reverse=True)[:5]
    
    return ranked_papers


def hierarchical_retrieve(
    query: str,
    alpha: float = 0.8,
    beta: float = 0.0,
    gamma: float = 0.0
) -> List[Dict]:
    """
    Execute hierarchical retrieval: title filtering -> abstract ranking.
    
    Args:
        query: User's search query
        alpha: Weight for semantic similarity (default 0.8)
        beta: Weight for recency (default 0.1)
        gamma: Weight for citations (default 0.1)
    
    Returns:
        Top 5 papers ranked by weighted composite score
    """
    # Stage 1: Retrieve up to 20 papers and rank by titles (keep top 10)
    papers = search_pubmed(query)
    if not papers:
        return []
    
    papers = rank_titles(query, papers)
    
    # Stage 2: Rank top 10 by abstracts (keep top 5) with weighted scoring
    papers = rank_abstracts(query, papers, alpha=0.9, beta=0.0, gamma=0.3)
    
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
    """Call the LLM to generate queries from clinical notes or analyze retrieved papers"""
    system_prompt = SystemMessage(
        content="""You are a biomedical literature retrieval and analysis expert.

## YOUR ROLE:

You assist doctors by:
1. Converting clinical notes into simple, effective PubMed search queries
2. Analyzing retrieved literature and providing clinical recommendations

## WHEN YOU RECEIVE A CLINICAL NOTE:

Extract the core medical problem and generate a SIMPLE search query:
- Keep queries SHORT (3-8 words maximum)
- Use broad medical terms, not specific drug names
- Focus on the disease/condition and treatment type
- Avoid over-specifying - PubMed works better with fewer terms
- Let PubMed's indexing do the work

Then invoke the tool:
<TOOL_CALL>
{"tool": "search_pubmed", "query": "YOUR_SIMPLE_QUERY"}
</TOOL_CALL>

-------------------------------------------------------------------------------
FEW-SHOT EXAMPLES
-------------------------------------------------------------------------------

Example 1

Input:
58-year-old male with type 2 diabetes and diabetic kidney disease.
Persistent albuminuria and declining eGFR despite ACE inhibitor therapy,
blood pressure control, and adequate glycemic management.

Clinical Question:
What therapies reduce albuminuria, preserve kidney function,
and improve long-term renal outcomes in diabetic kidney disease?

Query:
"diabetic kidney disease renal protective therapy"
-------------------------------------------------------------------------------

Example 2

Clinical Note:
54-year-old female with rheumatoid arthritis.
Persistent disease activity despite adequate methotrexate therapy.
Ongoing joint pain, morning stiffness, and elevated inflammatory markers.

Clinical Question:
What evidence supports escalation to biologic or targeted therapies after methotrexate failure?

Query:
"rheumatoid arthritis biologic therapy methotrexate failure"

-------------------------------------------------------------------------------
Example 3

Clinical Note:
62-year-old male with stage III non-small cell lung cancer.
Completed concurrent chemoradiotherapy.
No evidence of progression.
Question is whether immunotherapy consolidation should be added and what evidence supports its use.

Clinical Question:
What are the current immunotherapy strategies and outcomes for stage III NSCLC after chemoradiotherapy?

Query:
"stage III NSCLC immunotherapy consolidation"



## LITERATURE ANALYSIS

When ranked papers are returned, assume they have already been ranked by the retrieval system using semantic similarity, publication recency, and citation impact.

Do NOT re-rank papers.

Use the ranking provided.

For each paper report:

- Rank
- Title
- URL
- Publication Year
- Composite Score
- Citation Count

Then provide a concise evidence synthesis.

---

## REQUIRED OUTPUT FORMAT

### Top Ranked Papers

1. [Paper Title]
   - Rank: #
   - Composite Score: X.XXXX
   - Citations: N
   - Year: YYYY
   - URL: LINK

(repeat for all returned papers)

---

### Evidence Summary

Provide a concise synthesis of the literature.

Focus on:
- Major treatment strategies
- Consistent findings across studies
- Areas of agreement
- Areas of disagreement

---

### Comparative Findings

Summarize how the approaches differ.

Examples:
- Immunotherapy vs chemotherapy
- Targeted therapy vs standard care
- Combination therapy vs monotherapy

---

### Strength of Evidence

Discuss:

- Highly cited influential studies
- Recent studies that may represent current practice
- Whether evidence is mature or emerging

---

### Clinical Takeaways

Provide 3–5 practical clinical conclusions supported by the retrieved literature.

Base recommendations only on the retrieved papers.

---

### Limitations

Mention important limitations such as:

- Small sample sizes
- Early-phase trials
- Lack of long-term outcomes
- Limited generalizability
- Conflicting evidence

---

## IMPORTANT

Never invent study findings.

Only discuss evidence that can reasonably be inferred from the retrieved papers.

If abstracts are unavailable, clearly state that conclusions are limited.

Treat the retrieval ranking as authoritative and use it to guide emphasis during synthesis.

"""
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
                    
                    # Execute hierarchical retrieval directly in tool node
                    # This combines: search_pubmed -> rank_titles -> rank_abstracts
                    ranked_papers = hierarchical_retrieve(query)
                    
                    # Format the refined results with all metrics
                    formatted_results = format_ranked_papers(query, ranked_papers)
                    
                    # Return the refined top 5 papers with scores to the LLM
                    result_message = f"""
=== PUBMED SEARCH COMPLETE ===

{formatted_results}

"""
                    
                    # Add the tool result as a message
                    return {"messages": [HumanMessage(content=result_message)]}
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
    Format ranked papers for display with all metrics and weights.
    
    Args:
        query: Original search query
        papers: List of ranked papers with all scores
    
    Returns:
        Formatted string output
    """
    if not papers:
        return f"Query: {query}\n\nNo papers found."
    
    output = f"Query: {query}\n\n"
    output += "Top 5 Ranked Papers (By Weighted Composite Score)\n"
    output += "=" * 90 + "\n\n"
    
    # Display weights from first paper (same for all)
    if papers:
        alpha = papers[0].get('alpha', 0.8)
        beta = papers[0].get('beta', 0.1)
        gamma = papers[0].get('gamma', 0.1)
        total = alpha + beta + gamma
        alpha_norm = alpha / total if total > 0 else 0
        beta_norm = beta / total if total > 0 else 0
        gamma_norm = gamma / total if total > 0 else 0
        
        output += f"Scoring Weights (normalized):\n"
        output += f"  Alpha (Similarity):  {alpha_norm:.4f}\n"
        output += f"  Beta (Recency):      {beta_norm:.4f}\n"
        output += f"  Gamma (Citations):   {gamma_norm:.4f}\n"
        output += "\n" + "-" * 90 + "\n\n"
    
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
    # Initialize with a clinical note/query
    clinical_note = """
    58-year-old male with type 2 diabetes mellitus for 18 years.

Current medications:
- Metformin 1000 mg BID
- Ramipril 10 mg daily
- Amlodipine 5 mg daily
- Atorvastatin 40 mg daily

Clinical status:
- Persistent macroalbuminuria (UACR 850 mg/g)
- eGFR declined from 58 to 42 mL/min/1.73m² over the last 2 years
- HbA1c 6.9%
- Blood pressure 126/74 mmHg
- Potassium 4.6 mmol/L

Despite optimized ACE inhibitor therapy, blood pressure control, and acceptable glycemic control, kidney function continues to decline and albuminuria remains significantly elevated.

Clinical Question:
What evidence-based therapeutic strategies are available to reduce albuminuria, slow eGFR decline, decrease risk of progression to end-stage kidney disease, and improve long-term renal outcomes in patients with diabetic kidney disease already receiving standard-of-care therapy?

Please focus on:
- Additional pharmacologic interventions beyond ACE inhibitor therapy
- Renal outcome trials
- Albuminuria reduction
- Preservation of kidney function
- Combination treatment approaches
- Cardiovascular-kidney outcome benefits
- Current guideline-supported management strategies

Identify the strongest clinical evidence and the most relevant randomized trials for treatment decision-making."""
    
    print("=" * 100)
    print("BIOMEDICAL LITERATURE RETRIEVAL AGENT")
    print("=" * 100)
    print(f"\nClinical Note:\n{clinical_note}\n")
    print("-" * 100)
    print("Processing through agent graph...\n")
    
    # Initialize the agent state with the clinical note
    initial_state = {"messages": [HumanMessage(content=clinical_note)]}
    
    # Run the compiled graph
    final_result = compiled_graph.invoke(initial_state)
    
    # Extract and display the final LLM response
    print("\n" + "=" * 100)
    print("AGENT RESPONSE WITH CLINICAL ANALYSIS")
    print("=" * 100)
    
    for message in final_result["messages"]:
        if hasattr(message, 'content'):
            print(message.content)
    
    print("\n" + "=" * 100)
    print("WORKFLOW COMPLETE")
    print("=" * 100)