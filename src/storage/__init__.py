"""
Vector database integration for medical paper chunks.
Stores embeddings and metadata for semantic retrieval.
"""

from typing import List, Dict, Optional
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from src.config import QDRANT_COLLECTION_NAME, QDRANT_URL, EMBEDDING_DIMENSION, EMBEDDING_MODEL_NAME


class QdrantVectorStore:
    """Vector store for paper chunks using Qdrant."""
    
    def __init__(
        self,
        collection_name: str = QDRANT_COLLECTION_NAME,
        qdrant_url: str = QDRANT_URL,
        embedding_model_name: str = EMBEDDING_MODEL_NAME,
        embedding_dim: int = EMBEDDING_DIMENSION
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            collection_name: Name of Qdrant collection
            qdrant_url: URL of Qdrant server (use in-memory if None)
            embedding_model_name: Name of embedding model
            embedding_dim: Dimension of embeddings
        """
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        # Initialize Qdrant client
        try:
            # Try connecting to remote Qdrant server
            self.client = QdrantClient(url=qdrant_url, timeout=5)
            self.client.get_collections()  # Test connection
        except Exception:
            # Fall back to in-memory Qdrant
            self.client = QdrantClient(":memory:")
        
        # Create collection if it doesn't exist
        self._create_collection()
    
    def _create_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Collection doesn't exist, create it
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
    
    def add_chunks(self, chunks: List[Dict]) -> int:
        """
        Add chunks to vector store.
        
        Args:
            chunks: List of chunk dictionaries with 'text' and metadata
        
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        points = []
        
        for i, chunk in enumerate(chunks):
            # Generate embedding for chunk text
            embedding = self.embedding_model.encode(
                chunk['text'],
                normalize_embeddings=True
            ).tolist()
            
            # Create metadata (without large text field)
            metadata = {
                k: v for k, v in chunk.items() 
                if k != 'text' and k != 'embedding'
            }
            
            # Create point
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    **metadata,
                    'text': chunk['text']  # Include text in payload for retrieval
                }
            )
            points.append(point)
        
        # Upload points to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return len(points)
    
    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0
    ) -> List[Dict]:
        """
        Search for relevant chunks using semantic similarity.
        
        Args:
            query: Query text
            limit: Number of results to return
            score_threshold: Minimum similarity score
        
        Returns:
            List of relevant chunks with scores
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            query,
            normalize_embeddings=True
        ).tolist()
        
        # Search in Qdrant
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )
        
        # Extract results
        retrieved_chunks = []
        for result in results:
            chunk_data = result.payload
            retrieved_chunks.append({
                'score': result.score,
                'text': chunk_data.get('text', ''),
                'pmid': chunk_data.get('pmid'),
                'title': chunk_data.get('title'),
                'year': chunk_data.get('year'),
                'journal': chunk_data.get('journal'),
                'section': chunk_data.get('section'),
                'chunk_id': chunk_data.get('chunk_id')
            })
        
        return retrieved_chunks
    
    def clear_collection(self):
        """Clear all chunks from collection."""
        try:
            self.client.delete_collection(self.collection_name)
            self._create_collection()
        except Exception:
            pass
    
    def get_stats(self) -> Dict:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'collection_name': self.collection_name,
                'points_count': info.points_count,
                'vector_size': self.embedding_dim
            }
        except Exception:
            return {'error': 'Could not retrieve collection stats'}
