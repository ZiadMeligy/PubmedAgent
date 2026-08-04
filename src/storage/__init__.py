"""
Vector database integration for medical paper chunks.
Stores embeddings and metadata for semantic retrieval.
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path
import re
from typing import List, Dict, Optional
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchAny,
    MatchValue,
)
from src.config import QDRANT_COLLECTION_NAME, QDRANT_URL, EMBEDDING_DIMENSION, EMBEDDING_MODEL_NAME
from src.embeddings import embedding_model, get_embeddings


class QdrantVectorStore:
    """Vector store for paper chunks using Qdrant."""
    
    def __init__(
        self,
        collection_name: str = QDRANT_COLLECTION_NAME,
        qdrant_url: str = QDRANT_URL,
        embedding_dim: int = EMBEDDING_DIMENSION
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            collection_name: Name of Qdrant collection
            qdrant_url: URL of Qdrant server (use in-memory if None)
            embedding_dim: Dimension of embeddings
        """
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        # Reuse the shared singleton model from src.embeddings (already loaded, no deadlock)
        self.embedding_model = embedding_model
        
        # Initialize Qdrant client
        try:
            # Try connecting to remote Qdrant server
            self.client = QdrantClient(url=qdrant_url, timeout=5)
            self.client.get_collections()  # Test connection
        except Exception:
            # Keep the fallback persistent. A separate local path per logical
            # collection avoids Qdrant local-mode file-lock conflicts.
            safe_collection = re.sub(r"[^A-Za-z0-9._-]+", "_", collection_name)
            local_root = Path(
                os.getenv(
                    "QDRANT_LOCAL_PATH",
                    str(Path(__file__).resolve().parents[2] / "data" / "qdrant"),
                )
            )
            local_path = local_root / safe_collection
            local_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(local_path))
        
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
        score_threshold: float = 0.0,
        conversation_id: Optional[str] = None,
        pmids: Optional[List[str]] = None,
        content_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Search for relevant chunks using semantic similarity.
        
        Args:
            query: Query text
            limit: Number of results to return
            score_threshold: Minimum similarity score
            conversation_id: Optional conversation ID to filter by
        
        Returns:
            List of relevant chunks with scores
        """
        # Generate query embedding
        query_embedding = get_embeddings(
            [query],
            use_instruction=True,
        )[0].tolist()
        
        # Exact metadata filters are applied before vector similarity. This is
        # essential for ordinal questions such as "the third ranked paper".
        filter_conditions = []
        if conversation_id:
            filter_conditions.append(
                FieldCondition(
                    key="conversation_id",
                    match=MatchValue(value=conversation_id),
                )
            )
        if pmids:
            filter_conditions.append(
                FieldCondition(
                    key="pmid",
                    match=MatchAny(any=[str(pmid) for pmid in pmids]),
                )
            )
        if content_types:
            filter_conditions.append(
                FieldCondition(
                    key="content_type",
                    match=MatchAny(any=content_types),
                )
            )
        query_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Search in Qdrant
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True
        )
        
        # Extract results
        retrieved_chunks = []
        for result in results.points:
            chunk_data = dict(result.payload or {})
            chunk_data["score"] = result.score
            chunk_data.setdefault("text", "")
            retrieved_chunks.append(chunk_data)
        
        return retrieved_chunks

    def scroll_payloads(
        self,
        *,
        conversation_id: Optional[str] = None,
        pmids: Optional[List[str]] = None,
        limit: int = 512,
    ) -> List[Dict]:
        """Return payloads for a scoped lexical/hybrid retrieval pass."""
        conditions = []
        if conversation_id:
            conditions.append(
                FieldCondition(
                    key="conversation_id",
                    match=MatchValue(value=conversation_id),
                )
            )
        if pmids:
            conditions.append(
                FieldCondition(
                    key="pmid",
                    match=MatchAny(any=[str(pmid) for pmid in pmids]),
                )
            )
        query_filter = Filter(must=conditions) if conditions else None

        payloads = []
        offset = None
        while len(payloads) < limit:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=min(128, limit - len(payloads)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            payloads.extend(dict(point.payload or {}) for point in points)
            if offset is None or not points:
                break
        return payloads

    def delete_by_filter(
        self,
        *,
        conversation_id: Optional[str] = None,
        pmid: Optional[str] = None,
    ) -> None:
        """Delete a precisely scoped subset of points."""
        conditions = []
        if conversation_id:
            conditions.append(
                FieldCondition(
                    key="conversation_id",
                    match=MatchValue(value=conversation_id),
                )
            )
        if pmid:
            conditions.append(
                FieldCondition(key="pmid", match=MatchValue(value=str(pmid)))
            )
        if not conditions:
            raise ValueError("A conversation_id or pmid is required")
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=Filter(must=conditions)),
        )
    
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
