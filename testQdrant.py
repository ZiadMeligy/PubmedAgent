import uuid
from pathlib import Path
from typing import List, Dict

import fitz
from sentence_transformers import (
    SentenceTransformer,
    CrossEncoder
)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)


# ==========================================================
# PDF LOADER
# ==========================================================

class PDFLoader:

    @staticmethod
    def extract_text(pdf_path: str) -> str:

        doc = fitz.open(pdf_path)

        pages = []

        for page in doc:
            pages.append(page.get_text())

        doc.close()

        text = "\n".join(pages)

        return text


# ==========================================================
# TEXT CLEANING
# ==========================================================

class TextCleaner:

    @staticmethod
    def remove_front_matter(text: str) -> str:

        text_lower = text.lower()

        abstract_pos = text_lower.find("abstract")

        if abstract_pos != -1:
            text = text[abstract_pos:]

        return text


# ==========================================================
# CHUNKER
# ==========================================================

class TextChunker:

    def __init__(
        self,
        chunk_size: int = 250,
        overlap: int = 75
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict]:

        words = text.split()

        chunks = []

        start = 0
        chunk_id = 0

        while start < len(words):

            end = min(
                start + self.chunk_size,
                len(words)
            )

            chunk_text = " ".join(
                words[start:end]
            )

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text
                }
            )

            chunk_id += 1

            start += (
                self.chunk_size
                - self.overlap
            )

        return chunks


# ==========================================================
# VECTOR STORE
# ==========================================================

class QdrantVectorStore:

    def __init__(
        self,
        collection_name="agentic_ai_papers",
        qdrant_url="http://localhost:6333",
        embedding_model_name="BAAI/bge-small-en-v1.5"
    ):

        self.collection_name = collection_name

        print("Loading embedding model...")

        self.embedding_model = (
            SentenceTransformer(
                embedding_model_name
            )
        )

        print("Loading reranker...")

        self.reranker = CrossEncoder(
            "BAAI/bge-reranker-base"
        )

        self.embedding_dim = 384

        try:

            self.client = QdrantClient(
                url=qdrant_url,
                timeout=10
            )

            self.client.get_collections()

            print(
                "Connected to Qdrant server"
            )

        except Exception:

            print(
                "Using in-memory Qdrant"
            )

            self.client = QdrantClient(
                ":memory:"
            )

        self._create_collection()

    def _create_collection(self):

        collections = (
            self.client.get_collections()
        )

        existing = [
            c.name
            for c in collections.collections
        ]

        if self.collection_name in existing:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dim,
                distance=Distance.COSINE
            )
        )

    # ------------------------------------------------------

    def add_chunks(
        self,
        chunks: List[Dict]
    ):

        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        print(
            f"Generating embeddings for "
            f"{len(texts)} chunks..."
        )

        embeddings = (
            self.embedding_model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=True
            )
        )

        points = []

        for chunk, embedding in zip(
            chunks,
            embeddings
        ):

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload={
                        "chunk_id":
                            chunk["chunk_id"],
                        "text":
                            chunk["text"]
                    }
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        print(
            f"Inserted "
            f"{len(points)} chunks"
        )

    # ------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 5,
        candidate_count: int = 20
    ):

        query_embedding = (
            self.embedding_model.encode(
                query,
                normalize_embeddings=True
            ).tolist()
        )

        search_result = (
            self.client.query_points(
                collection_name=
                    self.collection_name,
                query=query_embedding,
                limit=candidate_count,
                with_payload=True
            )
        )

        candidates = []

        for point in search_result.points:

            candidates.append(
                {
                    "id": point.id,
                    "chunk_id":
                        point.payload.get(
                            "chunk_id"
                        ),
                    "text":
                        point.payload.get(
                            "text",
                            ""
                        ),
                    "vector_score":
                        float(point.score)
                }
            )

        if not candidates:
            return []

        print(
            f"Reranking "
            f"{len(candidates)} candidates..."
        )

        pairs = [
            (query, c["text"])
            for c in candidates
        ]

        rerank_scores = (
            self.reranker.predict(
                pairs
            )
        )

        for candidate, score in zip(
            candidates,
            rerank_scores
        ):

            candidate[
                "rerank_score"
            ] = float(score)

        candidates.sort(
            key=lambda x:
                x["rerank_score"],
            reverse=True
        )

        return candidates[:limit]

    # ------------------------------------------------------

    def stats(self):

        info = (
            self.client.get_collection(
                self.collection_name
            )
        )

        return {
            "collection":
                self.collection_name,
            "points":
                info.points_count
        }


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    PDF_PATH = (
        "Agentic_AI_Autonomous_Intelligence_"
        "for_Complex_GoalsA_Comprehensive_"
        "Survey.pdf"
    )

    if not Path(PDF_PATH).exists():

        raise FileNotFoundError(
            PDF_PATH
        )

    print("\nLoading PDF...")

    text = PDFLoader.extract_text(
        PDF_PATH
    )

    print(
        f"Extracted "
        f"{len(text):,} characters"
    )

    text = (
        TextCleaner
        .remove_front_matter(text)
    )

    chunker = TextChunker(
        chunk_size=250,
        overlap=75
    )

    chunks = chunker.chunk_text(
        text
    )

    print(
        f"Created "
        f"{len(chunks)} chunks"
    )

    vector_store = (
        QdrantVectorStore()
    )

    vector_store.add_chunks(
        chunks
    )

    print(
        "\nCollection Stats:"
    )

    print(
        vector_store.stats()
    )

    queries = [

        "What is Agentic AI?",

        "How do autonomous agents plan tasks?",

        "What are the challenges of agentic systems?",

        "What frameworks are discussed in the survey?",

        "What role does reinforcement learning play in Agentic AI?"
    ]

    for query in queries:

        print(
            "\n" +
            "=" * 80
        )

        print(
            f"\nQUERY:\n{query}"
        )

        results = (
            vector_store.search(
                query=query,
                limit=3,
                candidate_count=20
            )
        )

        for idx, result in enumerate(
            results,
            start=1
        ):

            print(
                f"\nResult {idx}"
            )

            print(
                f"Chunk: "
                f"{result['chunk_id']}"
            )

            print(
                f"Vector Score: "
                f"{result['vector_score']:.4f}"
            )

            print(
                f"Rerank Score: "
                f"{result['rerank_score']:.4f}"
            )

            print(
                result["text"][:700]
            )

            print("\n...")