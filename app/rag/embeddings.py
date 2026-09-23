"""
Embeddings Generation Module
Provides embedding vectors for RAG and semantic memory.
Supports OpenAI embeddings when OPENAI_API_KEY is configured,
with a robust normalized local embedding model as default.
"""
import os
import hashlib
import numpy as np
from typing import List
from app.config import settings

EMBEDDING_DIM = 384

class EmbeddingsProvider:
    """Provides vector embeddings with L2 normalization for cosine similarity search."""

    def __init__(self):
        self.dim = EMBEDDING_DIM
        self.use_openai = bool(settings.OPENAI_API_KEY)
        self._openai_client = None

    def _get_openai_client(self):
        if self._openai_client is None and self.use_openai:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def _local_embed(self, text: str) -> np.ndarray:
        """
        Deterministic, zero-dependency token-aware vectorizer with L2 normalization.
        Captures word frequencies, n-grams, and semantic sub-words into a fixed-dimension vector.
        """
        vector = np.zeros(self.dim, dtype=np.float32)
        words = [w.lower().strip(".,!?:;\"'()[]{}") for w in text.split()]
        words = [w for w in words if len(w) > 1]
        
        if not words:
            return vector

        for i, word in enumerate(words):
            # Primary word hash
            h1 = int(hashlib.sha256(word.encode("utf-8")).hexdigest()[:8], 16) % self.dim
            vector[h1] += 1.0

            # Substring/character trigrams for semantic/subword similarity
            if len(word) >= 3:
                for j in range(len(word) - 2):
                    trigram = word[j:j+3]
                    h2 = int(hashlib.md5(trigram.encode("utf-8")).hexdigest()[:8], 16) % self.dim
                    vector[h2] += 0.35

            # Word bi-gram with next word
            if i + 1 < len(words):
                bigram = f"{word}_{words[i+1]}"
                h3 = int(hashlib.sha1(bigram.encode("utf-8")).hexdigest()[:8], 16) % self.dim
                vector[h3] += 0.75

        # L2 normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding vector for a single text string."""
        if self.use_openai:
            try:
                client = self._get_openai_client()
                response = client.embeddings.create(
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    input=text
                )
                vec = np.array(response.data[0].embedding, dtype=np.float32)
                norm = np.linalg.norm(vec)
                return vec / norm if norm > 0 else vec
            except Exception:
                # Graceful fallback to local embed
                return self._local_embed(text)
        return self._local_embed(text)

    def get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        vectors = [self.get_embedding(t) for t in texts]
        return np.vstack(vectors).astype(np.float32)

embeddings_provider = EmbeddingsProvider()
