"""
FAISS Vector Store Manager
Maintains vector embeddings in FAISS IndexFlatIP (cosine similarity)
and maps vector entries back to Document Chunks, Documents, and Knowledge Bases.
"""
import os
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings

class FAISSVectorStore:
    """Manages persistent FAISS indexing, metadata mapping, and similarity search."""

    def __init__(self, storage_dir: Optional[Path] = None, dim: int = 384):
        self.storage_dir = storage_dir or settings.VECTOR_STORE_DIR
        self.dim = dim
        self.index_path = self.storage_dir / "knowledge_index.faiss"
        self.metadata_path = self.storage_dir / "vector_metadata.json"
        
        self.index = faiss.IndexFlatIP(self.dim)
        # Mapping from vector_id (int) to chunk metadata
        self.metadata_map: Dict[int, Dict[str, Any]] = {}
        
        self.load()

    def add_vectors(self, vectors: np.ndarray, metadata_list: List[Dict[str, Any]]) -> List[int]:
        """
        Add batch of vectors and corresponding metadata to the index.
        Returns assigned vector IDs.
        """
        if len(vectors) == 0:
            return []

        start_id = self.index.ntotal
        self.index.add(vectors.astype(np.float32))
        
        assigned_ids = []
        for i, meta in enumerate(metadata_list):
            vid = start_id + i
            self.metadata_map[vid] = meta
            assigned_ids.append(vid)

        self.save()
        return assigned_ids

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 4,
        kb_id: Optional[str] = None,
        min_score: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Search for most similar chunks, with optional knowledge base boundary enforcement.
        """
        if self.index.ntotal == 0:
            return []

        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        # Search extra candidates if filtering by knowledge base
        search_k = min(self.index.ntotal, max(top_k * 3, 20))
        scores, indices = self.index.search(query_vector, search_k)

        results = []
        for score, vid in zip(scores[0], indices[0]):
            if vid < 0 or vid not in self.metadata_map:
                continue
            
            meta = self.metadata_map[vid]
            # Knowledge base boundary filter
            if kb_id and meta.get("kb_id") != kb_id:
                continue
            
            if float(score) < min_score:
                continue

            results.append({
                "vector_id": int(vid),
                "score": round(float(score), 4),
                "chunk_id": meta.get("chunk_id"),
                "document_id": meta.get("document_id"),
                "kb_id": meta.get("kb_id"),
                "filename": meta.get("filename"),
                "chunk_index": meta.get("chunk_index"),
                "content": meta.get("content")
            })

            if len(results) >= top_k:
                break

        return results

    def clear(self):
        """Reset index and metadata."""
        self.index = faiss.IndexFlatIP(self.dim)
        self.metadata_map = {}
        self.save()

    def save(self):
        """Persist FAISS index and metadata to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.metadata_map.items()}, f, indent=2)

    def load(self):
        """Load index and metadata from disk if available."""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.metadata_map = {int(k): v for k, v in data.items()}
            except Exception:
                self.index = faiss.IndexFlatIP(self.dim)
                self.metadata_map = {}

vector_store = FAISSVectorStore()
