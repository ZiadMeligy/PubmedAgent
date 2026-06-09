import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from src.config import EMBEDDING_MODEL_NAME

# -------------------------
# BGE MODEL SETUP
# -------------------------
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


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
