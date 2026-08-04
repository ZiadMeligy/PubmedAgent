"""
Configuration and settings for the biomedical literature agent.
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# -------------------------
# LLM CONFIGURATION
# -------------------------

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
    temperature=0,
    # This application expects concise routing markers and JSON, not a visible
    # reasoning trace. Otherwise Qwen can spend the completion on <think> text
    # before producing the required output.
    reasoning_effort="none",
    reasoning_format="hidden",
    request_timeout=30,  # fail fast instead of hanging indefinitely
    max_retries=1,
)

# -------------------------
# EMBEDDINGS CONFIGURATION
# -------------------------

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSION = 384

# -------------------------
# RETRIEVAL CONFIGURATION
# -------------------------

PUBMED_MAX_RESULTS = 100
PUBMED_CHUNK_SIZE = 2
PUBMED_TITLE_TOP_K = 40
PUBMED_ABSTRACT_TOP_K = 5

# -------------------------
# SCORING WEIGHTS
# -------------------------

SCORE_ALPHA = 0.9  # Similarity weight
SCORE_BETA = 0.0   # Recency weight
SCORE_GAMMA = 0.3  # Citation weight
RECENCY_DECAY_RATE = 0.15
MAX_CITATIONS_REFERENCE = 10000

# -------------------------
# VECTOR STORE CONFIGURATION
# -------------------------

QDRANT_COLLECTION_NAME = "medical_papers"
QDRANT_URL = "http://localhost:6333"
VECTOR_STORE_THRESHOLD = 0.3
