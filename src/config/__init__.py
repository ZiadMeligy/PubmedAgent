"""
Configuration and settings for the biomedical literature agent.
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
# Hospital deployment template (leave commented while Groq is used):
# from langchain_ollama import ChatOllama

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

# -----------------------------------------------------------------
# OLLAMA / HOSPITAL LAN TEMPLATE — INACTIVE UNTIL MANUALLY ENABLED
# -----------------------------------------------------------------
# The URL is the Ollama workstation's LAN address and port. ChatOllama
# expects the server root URL, without a trailing "/api" or "/v1".
#
# OLLAMA_BASE_URL = os.getenv(
#     "OLLAMA_BASE_URL",
#     "http://MODEL_WORKSTATION_IP:11434",
# )
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.6:35b")
# OLLAMA_CONTEXT_LENGTH = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "32768"))
#
# To activate Ollama later:
# 1. Comment out the active ChatGroq `llm = ...` block above.
# 2. Uncomment the ChatOllama import and block below.
# 3. Set OLLAMA_BASE_URL to the model workstation's reachable LAN URL.
# 4. Ensure that exact OLLAMA_MODEL tag is already pulled on that workstation.
#
# llm = ChatOllama(
#     base_url=OLLAMA_BASE_URL,
#     model=OLLAMA_MODEL,
#     temperature=0,
#     reasoning=False,       # Return final content without a thinking trace.
#     num_ctx=OLLAMA_CONTEXT_LENGTH,
#     num_predict=2048,
#     keep_alive="30m",
# )

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
